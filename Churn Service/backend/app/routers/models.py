"""Model versions: list, metrics, HTML report, training, scoring, promotion and rollback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import jobs
from ..db import get_db
from ..models import User
from ..security import current_user, require_owner
from ..workspace import TRAINING_PROFILES, Workspace, org_lock
from .common import clean, records
from .jobs import JobOut, job_out

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_models(user: User = Depends(current_user)) -> dict:
    ws = Workspace(user.organization_id)
    table = ws.registry.list()
    return clean({"production": ws.production_version(), "versions": records(table) if len(table) else [],
                  "training_profiles": list(TRAINING_PROFILES)})


def _resolve(ws: Workspace, version: int) -> int:
    try:
        return ws.registry.resolve(version)
    except Exception:
        raise HTTPException(404, f"Model version {version} not found") from None


@router.get("/{version}")
def model_detail(version: int, user: User = Depends(current_user)) -> dict:
    ws = Workspace(user.organization_id)
    resolved = _resolve(ws, version)
    metrics = ws.registry.metrics(resolved)
    model = ws.model(resolved)
    return clean({
        "version": resolved,
        "is_production": resolved == ws.production_version(),
        "description": model.describe(),
        "test": metrics.get("test", {}),
        "validation": metrics.get("validation", {}),
        "leaderboard": metrics.get("leaderboard", []),
        "split": metrics.get("split", {}),
        "rows": metrics.get("rows", {}),
        "promotion": metrics.get("promotion", {}),
        "global_importance": metrics.get("global_importance", {}),
    })


@router.get("/{version}/report", response_class=HTMLResponse)
def model_report(version: int, user: User = Depends(current_user)) -> HTMLResponse:
    ws = Workspace(user.organization_id)
    path = ws.registry.version_dir(_resolve(ws, version)) / "report.html"
    if not path.exists():
        raise HTTPException(404, "Report not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


def _guard_idle(db: Session, org_id: int) -> None:
    if jobs.active_job(db, org_id) is not None or org_lock(org_id).locked():
        raise HTTPException(status.HTTP_409_CONFLICT, "A data load or training job is already running")


@router.post("/train", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def train(profile: str = Form("quick"), user: User = Depends(require_owner), db: Session = Depends(get_db)) -> JobOut:
    if profile not in TRAINING_PROFILES:
        raise HTTPException(422, f"profile must be one of {list(TRAINING_PROFILES)}")
    if not Workspace(user.organization_id).has_data():
        raise HTTPException(status.HTTP_409_CONFLICT, "Load data before training")
    _guard_idle(db, user.organization_id)
    return job_out(jobs.submit(db, user.organization_id, user.id, "train", {"profile": profile}))


@router.post("/score", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def score(user: User = Depends(require_owner), db: Session = Depends(get_db)) -> JobOut:
    if Workspace(user.organization_id).production_version() is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Train a model before scoring")
    return job_out(jobs.submit(db, user.organization_id, user.id, "score", {}))


@router.post("/{version}/promote")
def promote(version: int, user: User = Depends(require_owner), db: Session = Depends(get_db)) -> dict:
    ws = Workspace(user.organization_id)
    ws.registry.promote(_resolve(ws, version), reason=f"promoted by {user.email}")
    job = jobs.submit(db, user.organization_id, user.id, "score", {})  # rescore with the new production model
    return {"production": ws.production_version(), "rescore_job": job.id}


@router.post("/rollback")
def rollback(user: User = Depends(require_owner), db: Session = Depends(get_db)) -> dict:
    ws = Workspace(user.organization_id)
    try:
        version = ws.registry.rollback()
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    job = jobs.submit(db, user.organization_id, user.id, "score", {})
    return {"production": version, "rescore_job": job.id}
