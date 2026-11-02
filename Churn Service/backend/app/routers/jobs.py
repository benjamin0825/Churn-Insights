"""Background job status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Job, User
from ..security import current_user

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: int
    kind: str
    status: str
    message: str
    params: dict[str, Any]
    result: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def job_out(job: Job) -> JobOut:
    params = {k: v for k, v in (job.params or {}).items() if k != "user_id"}
    return JobOut(id=job.id, kind=job.kind, status=job.status, message=job.message, params=params,
                  result=job.result or {}, error=job.error, created_at=job.created_at, started_at=job.started_at,
                  finished_at=job.finished_at)


@router.get("", response_model=list[JobOut])
def list_jobs(limit: int = 20, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[JobOut]:
    rows = (db.query(Job).filter(Job.organization_id == user.organization_id).order_by(Job.id.desc())
            .limit(min(max(limit, 1), 100)).all())
    return [job_out(j) for j in rows]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None or job.organization_id != user.organization_id:
        raise HTTPException(404, "Job not found")
    return job_out(job)
