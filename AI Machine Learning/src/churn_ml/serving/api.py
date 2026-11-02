"""Churn prediction service.

churn-ml serve                       # or
uvicorn churn_ml.serving.api:app     # uses CHURN_ML_PROFILE / default config
"""

import os
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .. import __version__
from ..data.validation import DataValidationError
from ..explain.shap_explainer import try_explainer
from ..features.builder import FeatureBuilder
from ..features.spec import FeatureSpec
from ..logging_utils import get_logger
from ..registry.model_registry import ModelRegistry, RegistryError
from ..settings import Settings, load_settings
from ..training.dataset import load_raw
from .schemas import (
    CustomerScoreRequest,
    CustomerScoreResponse,
    DriftResponse,
    ModelInfo,
    PredictionResponse,
    feature_record_model,
)

log = get_logger(__name__)


class Metrics:
    """Minimal Prometheus text-format counters (no extra dependency)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self.latency_sum: dict[str, float] = defaultdict(float)
        self.latency_count: dict[str, int] = defaultdict(int)
        self.predictions = 0

    def observe(self, method: str, path: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[(method, path, status)] += 1
            self.latency_sum[path] += seconds
            self.latency_count[path] += 1

    def render(self, model_version: int | None) -> str:
        lines = ["# TYPE churn_http_requests_total counter"]
        for (method, path, status), n in sorted(self.requests.items()):
            lines.append(f'churn_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {n}')
        lines.append("# TYPE churn_http_request_seconds summary")
        for path in sorted(self.latency_sum):
            lines.append(f'churn_http_request_seconds_sum{{path="{path}"}} {self.latency_sum[path]:.6f}')
            lines.append(f'churn_http_request_seconds_count{{path="{path}"}} {self.latency_count[path]}')
        lines += [
            "# TYPE churn_predictions_total counter",
            f"churn_predictions_total {self.predictions}",
            "# TYPE churn_model_version gauge",
            f"churn_model_version {model_version or 0}",
        ]
        return "\n".join(lines) + "\n"


class ServiceState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = ModelRegistry(settings.registry_dir)
        self.model = None
        self.version: int | None = None
        self.explainer = None
        self._builder: FeatureBuilder | None = None
        self.metrics = Metrics()

    def reload(self) -> int:
        registry = ModelRegistry(self.settings.registry_dir)  # fresh cache
        version = registry.resolve("production")
        self.model, self.version, self.registry = registry.load(version), version, registry
        self.explainer = try_explainer(self.model)
        log.info("serving model v%04d", version)
        return version

    def require_model(self):
        if self.model is None:
            try:
                self.reload()
            except RegistryError as exc:
                raise HTTPException(503, str(exc)) from exc
        return self.model

    def builder(self) -> FeatureBuilder:
        if self._builder is None:
            try:
                data = load_raw(self.settings)
            except FileNotFoundError as exc:
                raise HTTPException(503, str(exc)) from exc
            self._builder = FeatureBuilder(data, self.settings.features, self.settings.labeling.horizon_weeks)
        return self._builder


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings(os.environ.get("CHURN_ML_PROFILE"))
    state = ServiceState(settings)
    FeatureRecord = feature_record_model(FeatureSpec.from_config(settings.features))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            state.reload()
        except RegistryError as exc:
            log.warning("starting without a model: %s", exc)
        yield

    app = FastAPI(title="Churn Prediction Service", version=__version__, lifespan=lifespan)
    app.state.service = state

    @app.middleware("http")
    async def record_metrics(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        state.metrics.observe(request.method, path, response.status_code, time.perf_counter() - start)
        return response

    def _predict(frame: pd.DataFrame, explain: bool) -> list[dict]:
        model = state.require_model()
        try:
            scores = model.score(frame)
        except DataValidationError as exc:
            raise HTTPException(422, {"validation_errors": exc.report.errors}) from exc
        records = scores.to_dict(orient="records")
        if explain:
            if state.explainer is None:
                raise HTTPException(409, "the production model has no tree member to explain")
            for record, reasons in zip(records, state.explainer.reasons(frame, settings.explain.top_reasons)):
                record["reasons"] = reasons
        state.metrics.predictions += len(records)
        return records

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok" if state.model is not None else "no-model",
            "model_version": state.version,
            "package_version": __version__,
        }

    @app.get("/model", response_model=ModelInfo)
    def model_info() -> dict:
        model = state.require_model()
        metrics = state.registry.metrics(state.version)
        spec = model.spec
        return {
            "version": state.version,
            "description": model.describe(),
            "test_metrics": metrics["test"],
            "features": {"numeric": spec.numeric, "categorical": spec.categorical, "text": spec.text},
        }

    @app.post("/predict", response_model=PredictionResponse)
    def predict(records: list[FeatureRecord], explain: bool = False) -> dict:  # type: ignore[valid-type]
        if not records:
            raise HTTPException(422, "provide at least one record")
        if len(records) > 5000:
            raise HTTPException(413, "at most 5000 records per request")
        frame = pd.DataFrame([r.model_dump() for r in records])
        predictions = _predict(frame, explain)
        return {"model_version": state.version, "threshold": state.model.threshold, "predictions": predictions}

    @app.post("/customers/score", response_model=CustomerScoreResponse)
    def score_customers(body: CustomerScoreRequest) -> dict:
        builder = state.builder()
        week = builder.n_weeks if body.as_of_week is None else body.as_of_week
        if not 0 < week <= builder.n_weeks:
            raise HTTPException(422, f"as_of_week must be in 1..{builder.n_weeks}")
        snapshot = builder.build_snapshot(week)
        wanted = set(body.customer_ids)
        frame = snapshot[snapshot["customer_id"].isin(wanted)].reset_index(drop=True)
        not_found = sorted(wanted - set(frame["customer_id"]))
        predictions = _predict(frame, body.explain) if len(frame) else []
        return {
            "model_version": state.version,
            "threshold": state.require_model().threshold,
            "as_of_week": week,
            "not_found": not_found,
            "predictions": predictions,
        }

    @app.post("/drift", response_model=DriftResponse)
    def drift(records: list[FeatureRecord]) -> dict:  # type: ignore[valid-type]
        model = state.require_model()
        if len(records) < 50:
            raise HTTPException(422, "drift needs at least 50 records to be meaningful")
        frame = pd.DataFrame([r.model_dump() for r in records])
        mon = settings.monitoring
        report = model.drift_profile.compare(frame, model.predict_proba(frame), mon.psi_warning, mon.psi_alert)
        return {"model_version": state.version, **report.to_dict()}

    @app.post("/admin/reload")
    def reload() -> dict:
        try:
            return {"model_version": state.reload()}
        except RegistryError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return state.metrics.render(state.version)

    return app


def __getattr__(name: str):
    # ``uvicorn churn_ml.serving.api:app`` builds the app lazily so importing this module stays cheap.
    if name == "app":
        return create_app()
    raise AttributeError(name)
