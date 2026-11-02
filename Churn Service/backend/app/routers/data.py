"""Data management: status, CSV upload, demo data and CSV templates."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import jobs
from ..config import get_settings
from ..db import get_db
from ..ingest import TABLES, IngestError, ingest_csv, to_csv_tables
from ..models import Dataset, Job, User
from ..security import current_user, require_owner
from ..workspace import TRAINING_PROFILES, Workspace, org_lock
from .common import clean
from .jobs import JobOut, job_out

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/status")
def data_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    ws = Workspace(user.organization_id)
    latest = (db.query(Dataset).filter(Dataset.organization_id == user.organization_id)
              .order_by(Dataset.id.desc()).first())
    active = jobs.active_job(db, user.organization_id)
    last = db.query(Job).filter(Job.organization_id == user.organization_id).order_by(Job.id.desc()).first()
    return clean({
        "has_data": ws.has_data(),
        "has_model": ws.production_version() is not None,
        "has_scores": ws.latest_meta() is not None,
        "dataset": None if latest is None else {"id": latest.id, "source": latest.source,
                                                "created_at": latest.created_at.isoformat(),
                                                "summary": latest.summary, "warnings": latest.warnings},
        "active_job": None if active is None else job_out(active).model_dump(mode="json"),
        "last_job": None if last is None else job_out(last).model_dump(mode="json"),
        "training_profiles": list(TRAINING_PROFILES),
    })


@router.get("/datasets")
def datasets(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = (db.query(Dataset).filter(Dataset.organization_id == user.organization_id)
            .order_by(Dataset.id.desc()).limit(50).all())
    return clean([{"id": d.id, "source": d.source, "created_at": d.created_at.isoformat(), "summary": d.summary,
                   "warnings": d.warnings} for d in rows])


def _guard_idle(db: Session, org_id: int) -> None:
    if jobs.active_job(db, org_id) is not None or org_lock(org_id).locked():
        raise HTTPException(status.HTTP_409_CONFLICT, "A data load or training job is already running")


@router.post("/demo", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def load_demo(customers: int = Form(10000, ge=500, le=50000), profile: str = Form("quick"),
              user: User = Depends(require_owner), db: Session = Depends(get_db)) -> JobOut:
    if profile not in TRAINING_PROFILES:
        raise HTTPException(422, f"profile must be one of {list(TRAINING_PROFILES)}")
    _guard_idle(db, user.organization_id)
    job = jobs.submit(db, user.organization_id, user.id, "demo",
                      {"customers": customers, "profile": profile, "user_id": user.id})
    return job_out(job)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload(customers: UploadFile = File(...), usage: UploadFile = File(...), billing: UploadFile = File(...),
                 tickets: UploadFile = File(...), train: bool = Form(True), profile: str = Form("quick"),
                 user: User = Depends(require_owner), db: Session = Depends(get_db)) -> dict:
    if profile not in TRAINING_PROFILES:
        raise HTTPException(422, f"profile must be one of {list(TRAINING_PROFILES)}")
    _guard_idle(db, user.organization_id)
    limit = get_settings().max_upload_mb * 1024 * 1024
    files: dict[str, bytes] = {}
    for name, upload_file in zip(TABLES, (customers, usage, billing, tickets)):
        content = await upload_file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                f"{name}.csv is larger than {get_settings().max_upload_mb} MB")
        files[name] = content
    try:
        result = ingest_csv(files, get_settings().min_history_weeks)
    except IngestError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"errors": exc.errors}) from None

    ws = Workspace(user.organization_id)
    with org_lock(user.organization_id):
        ws.save_raw(result.data, {"n_weeks": result.n_weeks, "start_date": result.start_date.date().isoformat(),
                                  "source": "upload"})
    dataset = Dataset(organization_id=user.organization_id, source="upload", summary=result.summary(),
                      warnings=result.warnings, created_by=user.id)
    db.add(dataset)
    db.commit()
    warnings = list(result.warnings)
    blocker = jobs.training_blocker(int(result.summary().get("churned_customers", 0))) if train else None
    if blocker:
        warnings.append(f"Training was skipped. {blocker}")
    job = jobs.submit(db, user.organization_id, user.id, "train", {"profile": profile}) if train and not blocker else None
    return clean({"dataset_id": dataset.id, "summary": result.summary(), "warnings": warnings,
                  "job": None if job is None else job_out(job).model_dump(mode="json")})


@router.get("/template/{table}", response_class=PlainTextResponse)
def template(table: str, user: User = Depends(current_user)) -> PlainTextResponse:
    """A small, realistic sample of one upload file (40 customers), in the exact upload format."""
    if table not in TABLES:
        raise HTTPException(404, f"unknown table; use one of {list(TABLES)}")
    tables = _sample_tables()
    return PlainTextResponse(tables[table], media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{table}.csv"'})


_SAMPLE: dict[str, str] | None = None


def _sample_tables() -> dict[str, str]:
    global _SAMPLE
    if _SAMPLE is None:
        from churn_ml.data.simulator import simulate
        from churn_ml.settings import SimulationConfig

        cfg = SimulationConfig(n_customers=300, new_customers_per_week=2, n_weeks=60)
        _SAMPLE = to_csv_tables(simulate(cfg, seed=7), pd.Timestamp(cfg.start_date), limit_customers=40)
    return _SAMPLE
