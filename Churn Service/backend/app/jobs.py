"""Background jobs: demo data, training, scoring and drift monitoring.

Jobs run in a small thread pool so API requests stay fast. Each job records its
status in the ``jobs`` table; heavy jobs take the organization's lock, so one
organization never trains twice at the same time.
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd
from churn_ml.data.simulator import simulate
from churn_ml.scoring import attach_reasons, monitor_batch
from churn_ml.settings import SimulationConfig
from churn_ml.training.dataset import build_scoring_frame
from churn_ml.training.trainer import train
from sqlalchemy.orm import Session

from .config import get_settings
from .db import session_factory
from .models import Dataset, Job, utcnow
from .workspace import LATEST_FEATURES, LATEST_META, LATEST_SCORES, TRAINING_PROFILES, Workspace, org_lock

log = logging.getLogger(__name__)
_executor: ThreadPoolExecutor | None = None
JOB_KINDS = ("demo", "train", "score", "monitor")
# A model needs customers who left to learn from; below this, training can't produce a useful model.
MIN_CHURNED_FOR_TRAINING = 30


class JobError(Exception):
    """A failure the user can act on; its message is shown as is, without a traceback."""


def training_blocker(churned_customers: int) -> str | None:
    """Why this dataset can't be trained on, in plain words, or None if it can."""
    if churned_customers >= MIN_CHURNED_FOR_TRAINING:
        return None
    return (f"Only {churned_customers} customer{'s' if churned_customers != 1 else ''} in this data left during the history, "
            f"and at least {MIN_CHURNED_FOR_TRAINING} are needed to train a model. Upload data with more customers or a "
            "longer history, or try the demo data.")


def executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=get_settings().job_workers, thread_name_prefix="job")
    return _executor


def _update(job_id: int, **fields: Any) -> None:
    with session_factory()() as db:
        job = db.get(Job, job_id)
        for key, value in fields.items():
            setattr(job, key, value)
        db.commit()


def _run(job_id: int, org_id: int, func: Callable[[Workspace, Callable[[str], None], dict], dict], params: dict):
    progress = lambda message: _update(job_id, message=message[:500])  # noqa: E731
    _update(job_id, status="running", started_at=utcnow(), message="starting")
    try:
        with org_lock(org_id):
            result = func(Workspace(org_id), progress, params)
        _update(job_id, status="succeeded", finished_at=utcnow(), message="done", result=result or {})
    except JobError as exc:  # expected and explained to the user
        log.info("job %s stopped: %s", job_id, exc)
        _update(job_id, status="failed", finished_at=utcnow(), message="failed", error=str(exc)[:8000])
    except Exception as exc:  # recorded for the UI; the worker thread keeps running
        log.exception("job %s failed", job_id)
        _update(job_id, status="failed", finished_at=utcnow(), message="failed",
                error=f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc(limit=5)}"[:8000])


def submit(db: Session, org_id: int, user_id: int | None, kind: str, params: dict | None = None,
           run_inline: bool = False) -> Job:
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown job kind {kind!r}")
    job = Job(organization_id=org_id, kind=kind, params=params or {}, created_by=user_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    func = {"demo": run_demo, "train": run_train, "score": run_score, "monitor": run_monitor}[kind]
    if run_inline:  # tests
        _run(job.id, org_id, func, job.params)
        db.refresh(job)
    else:
        executor().submit(_run, job.id, org_id, func, job.params)
    return job


def active_job(db: Session, org_id: int, kinds: tuple[str, ...] = ("demo", "train")) -> Job | None:
    return (db.query(Job).filter(Job.organization_id == org_id, Job.kind.in_(kinds),
                                 Job.status.in_(("queued", "running"))).order_by(Job.id.desc()).first())


# ------------------------------------------------------------------ job bodies
def run_demo(ws: Workspace, progress, params: dict) -> dict:
    """Generate a realistic demo dataset, then train and score so the dashboard is populated."""
    progress("generating demo customers, usage, billing and tickets")
    customers = int(params.get("customers", get_settings().demo_customers))
    cfg = SimulationConfig(n_customers=customers, new_customers_per_week=max(1, customers // 160))
    data = simulate(cfg, seed=int(params.get("seed", 42)))
    meta = {"n_weeks": cfg.n_weeks, "start_date": str(cfg.start_date), "source": "demo"}
    ws.save_raw(data, meta)
    _record_dataset(ws.org_id, "demo", {**data.summary(), "n_weeks": cfg.n_weeks, "start_date": str(cfg.start_date)},
                    [], params.get("user_id"))
    result = run_train(ws, progress, {"profile": params.get("profile", "quick")})
    return {"dataset": data.summary(), **result}


def run_train(ws: Workspace, progress, params: dict) -> dict:
    profile = params.get("profile", "quick")
    if profile not in TRAINING_PROFILES:
        raise ValueError(f"unknown training profile {profile!r}")
    if not ws.has_data():
        raise JobError("No data is loaded yet. Upload your CSV files or load the demo data first.")
    raw = ws.raw()
    blocker = training_blocker(int(raw.customers["churn_week"].notna().sum()))
    if blocker:
        raise JobError(blocker)
    settings = ws.settings(profile)
    progress(f"training ({profile}): building features, tuning {len(settings.models.enabled)} model families")
    try:
        outcome = train(settings, raw)
    except ValueError as exc:
        if "class" in str(exc):  # every training example had the same outcome
            raise JobError("None of the customers in the training window left, so there is nothing to learn from yet. "
                           "Upload data that covers a longer history or more customers.") from exc
        raise
    progress("scoring customers with the new model")
    score = run_score(ws, progress, {})
    progress("checking drift")
    drift = run_monitor(ws, progress, {})
    test = outcome.metrics["test"]
    return {
        "version": outcome.version, "promoted": outcome.promoted, "decision": outcome.decision["reason"],
        "test_roc_auc": round(test["roc_auc"], 4), "test_average_precision": round(test["average_precision"], 4),
        "lift_at_10pct": round(test["lift_at_10pct"], 2), "scored": score.get("customers"),
        "drift_status": drift.get("status"),
    }


def run_score(ws: Workspace, progress, params: dict) -> dict:
    version = ws.production_version()
    if version is None:
        raise RuntimeError("no production model; train one first")
    settings = ws.settings()
    model = ws.model(version)
    progress(f"building features and scoring with model v{version:04d}")
    features, week = build_scoring_frame(settings, ws.raw(), params.get("week"))
    scores = attach_reasons(model, features, model.score(features), settings.explain.top_reasons,
                            only_tiers=("high",))
    out = ws.predictions_dir
    out.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(out / LATEST_SCORES, index=False)
    features.to_parquet(out / LATEST_FEATURES, index=False)
    meta = {"week": week, "model_version": version, "scored_at": utcnow().isoformat(timespec="seconds"),
            "customers": len(scores), "tiers": scores["risk_tier"].value_counts().to_dict()}
    (out / LATEST_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def run_monitor(ws: Workspace, progress, params: dict) -> dict:
    if ws.production_version() is None:
        raise RuntimeError("no production model; train one first")
    result = monitor_batch(ws.settings(), params.get("week"))
    return {"status": result.report.status, "week": result.week, "version": result.version,
            "drifted_features": result.report.drifted_features[:10]}


def _record_dataset(org_id: int, source: str, summary: dict, warnings: list[str], user_id: int | None) -> None:
    with session_factory()() as db:
        db.add(Dataset(organization_id=org_id, source=source, summary=summary, warnings=warnings, created_by=user_id))
        db.commit()


def history_frame(ws: Workspace, customer_id: int) -> dict[str, pd.DataFrame]:
    raw = ws.raw()
    return {name: getattr(raw, name)[getattr(raw, name)["customer_id"] == customer_id]
            for name in ("usage", "billing", "tickets")}
