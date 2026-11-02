"""Drift monitoring: latest report and on-demand runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import jobs
from ..db import get_db
from ..models import User
from ..security import current_user, require_owner
from ..workspace import Workspace
from .common import clean
from .jobs import JobOut, job_out

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/drift")
def latest_drift(user: User = Depends(current_user)) -> dict:
    report = Workspace(user.organization_id).latest_drift()
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No drift report yet")
    return clean(report)


@router.get("/drift/report", response_class=HTMLResponse)
def latest_drift_html(user: User = Depends(current_user)) -> HTMLResponse:
    report = Workspace(user.organization_id).latest_drift()
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No drift report yet")
    html = Workspace(user.organization_id).monitoring_dir / report["report_file"].replace(".json", ".html")
    if not html.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report file missing")
    return HTMLResponse(html.read_text(encoding="utf-8"))


@router.post("/run", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def run(user: User = Depends(require_owner), db: Session = Depends(get_db)) -> JobOut:
    if Workspace(user.organization_id).production_version() is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Train a model before monitoring")
    return job_out(jobs.submit(db, user.organization_id, user.id, "monitor", {}))
