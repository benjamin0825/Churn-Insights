"""Careers: public job postings and applications, managed from the admin panel.

Public routes need no login. Applications (with an optional CV) are stored under
``data_dir/applications`` and are only readable by site admins.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import JobApplication, JobPosting, utcnow
from ..security import require_admin

public = APIRouter(prefix="/api/careers", tags=["careers"])
admin = APIRouter(prefix="/api/admin/careers", tags=["admin"], dependencies=[Depends(require_admin)])

Workplace = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship"]
PostingStatus = Literal["draft", "open", "closed"]
ApplicationStatus = Literal["new", "reviewing", "interview", "offer", "hired", "rejected"]

MAX_RESUME_BYTES = 5 * 1024 * 1024
# Accepted CV formats, checked by content as well as by extension.
RESUME_SIGNATURES = {".pdf": (b"%PDF",), ".docx": (b"PK\x03\x04",), ".doc": (b"\xd0\xcf\x11\xe0",)}
APPLY_LIMIT, APPLY_WINDOW_S = 5, 600  # per client address


# ------------------------------------------------------------------ schemas
class PostingIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    department: str = Field("Engineering", max_length=80)
    location: str = Field("Remote", max_length=120)
    workplace: Workplace = "remote"
    employment_type: EmploymentType = "full_time"
    salary_range: str = Field("", max_length=120)
    summary: str = Field("", max_length=400)
    description: str = Field("", max_length=20000)
    responsibilities: list[str] = Field(default_factory=list, max_length=30)
    requirements: list[str] = Field(default_factory=list, max_length=30)
    nice_to_have: list[str] = Field(default_factory=list, max_length=30)
    benefits: list[str] = Field(default_factory=list, max_length=30)
    status: PostingStatus = "draft"


class PostingOut(PostingIn):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class AdminPostingOut(PostingOut):
    applications: int = 0
    new_applications: int = 0


class ApplicationOut(BaseModel):
    id: int
    posting_id: int
    posting_title: str
    name: str
    email: str
    phone: str
    location: str
    linkedin_url: str
    portfolio_url: str
    cover_letter: str
    has_resume: bool
    resume_filename: str
    status: ApplicationStatus
    notes: str
    created_at: datetime


class ApplicationPatch(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = Field(None, max_length=10000)


def _items(values: list[str]) -> list[str]:
    return [re.sub(r"\s+", " ", v).strip()[:300] for v in values if v.strip()]


def _posting_out(p: JobPosting) -> PostingOut:
    return PostingOut(id=p.id, slug=p.slug, title=p.title, department=p.department, location=p.location,
                      workplace=p.workplace, employment_type=p.employment_type, salary_range=p.salary_range,
                      summary=p.summary, description=p.description, responsibilities=p.responsibilities or [],
                      requirements=p.requirements or [], nice_to_have=p.nice_to_have or [], benefits=p.benefits or [],
                      status=p.status, created_at=p.created_at, updated_at=p.updated_at, published_at=p.published_at)


def _application_out(a: JobApplication, title: str) -> ApplicationOut:
    return ApplicationOut(id=a.id, posting_id=a.posting_id, posting_title=title, name=a.name, email=a.email,
                          phone=a.phone, location=a.location, linkedin_url=a.linkedin_url, portfolio_url=a.portfolio_url,
                          cover_letter=a.cover_letter, has_resume=bool(a.resume_path), resume_filename=a.resume_filename,
                          status=a.status, notes=a.notes, created_at=a.created_at)


def _slugify(db: Session, title: str, current_id: int | None = None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "position"
    slug, n = base, 2
    while (other := db.query(JobPosting).filter(JobPosting.slug == slug).first()) and other.id != current_id:
        slug, n = f"{base}-{n}", n + 1
    return slug


# ------------------------------------------------------------------ public
@public.get("", response_model=list[PostingOut])
def open_postings(db: Session = Depends(get_db)) -> list[PostingOut]:
    rows = (db.query(JobPosting).filter(JobPosting.status == "open")
            .order_by(JobPosting.department, JobPosting.published_at.desc()))
    return [_posting_out(p) for p in rows]


def _open_posting(db: Session, slug: str) -> JobPosting:
    posting = db.query(JobPosting).filter(JobPosting.slug == slug).first()
    if posting is None or posting.status == "draft":
        raise HTTPException(404, "This position doesn't exist")
    return posting


@public.get("/{slug}", response_model=PostingOut)
def posting_detail(slug: str, db: Session = Depends(get_db)) -> PostingOut:
    """Closed postings stay readable (links keep working) but can't be applied to."""
    return _posting_out(_open_posting(db, slug))


_recent: dict[str, deque[float]] = defaultdict(deque)
_recent_guard = threading.Lock()


def _rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _recent_guard:
        hits = _recent[key]
        while hits and now - hits[0] > APPLY_WINDOW_S:
            hits.popleft()
        if len(hits) >= APPLY_LIMIT:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many applications from this address; try again later")
        hits.append(now)


def _url(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = f"https://{value}"
    if len(value) > 500 or not re.match(r"^https?://[^\s/$.?#][^\s]*$", value, re.I):
        raise HTTPException(422, f"{field} must be a web address")
    return value


@public.post("/{slug}/apply", status_code=status.HTTP_201_CREATED)
async def apply(slug: str, request: Request,
                name: str = Form(..., min_length=2, max_length=200), email: str = Form(..., max_length=320),
                phone: str = Form("", max_length=50), location: str = Form("", max_length=120),
                linkedin_url: str = Form("", max_length=500), portfolio_url: str = Form("", max_length=500),
                cover_letter: str = Form("", max_length=10000), website: str = Form(""),
                resume: UploadFile | None = File(None), db: Session = Depends(get_db)) -> dict:
    posting = _open_posting(db, slug)
    if posting.status != "open":
        raise HTTPException(409, "This position is no longer accepting applications")
    if website:  # honeypot field, hidden from people; bots fill it in
        return {"ok": True}
    _rate_limit(request)
    try:
        email = TypeAdapter(EmailStr).validate_python(email.strip()).lower()
    except ValidationError:
        raise HTTPException(422, "Please enter a valid email address") from None

    application = JobApplication(posting_id=posting.id, name=name.strip(), email=email, phone=phone.strip(),
                                 location=location.strip(), linkedin_url=_url(linkedin_url, "LinkedIn"),
                                 portfolio_url=_url(portfolio_url, "Portfolio / GitHub"), cover_letter=cover_letter.strip())
    content = b""
    if resume is not None and resume.filename:
        suffix = Path(resume.filename).suffix.lower()
        if suffix not in RESUME_SIGNATURES:
            raise HTTPException(422, "Your CV must be a PDF or Word document (.pdf, .docx or .doc)")
        content = await resume.read(MAX_RESUME_BYTES + 1)
        if len(content) > MAX_RESUME_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Your CV must be 5 MB or smaller")
        if not content.startswith(RESUME_SIGNATURES[suffix]):
            raise HTTPException(422, f"That file doesn't look like a {suffix} document")
        # Stored under a random name; the original name is kept only for the download.
        stored = Path("applications") / f"{posting.id:05d}" / f"{secrets.token_hex(12)}{suffix}"
        application.resume_path = stored.as_posix()
        application.resume_filename = re.sub(r"[^\w.\- ]+", "_", Path(resume.filename).name)[:200]
    db.add(application)
    db.commit()
    if content:
        target = get_settings().data_dir / application.resume_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return {"ok": True, "id": application.id}


# ------------------------------------------------------------------ admin
def _counts(db: Session) -> tuple[dict[int, int], dict[int, int]]:
    total = dict(db.query(JobApplication.posting_id, func.count()).group_by(JobApplication.posting_id).all())
    new = dict(db.query(JobApplication.posting_id, func.count()).filter(JobApplication.status == "new")
               .group_by(JobApplication.posting_id).all())
    return total, new


def _admin_out(p: JobPosting, total: dict[int, int], new: dict[int, int]) -> AdminPostingOut:
    return AdminPostingOut(**_posting_out(p).model_dump(), applications=total.get(p.id, 0),
                           new_applications=new.get(p.id, 0))


@admin.get("/postings", response_model=list[AdminPostingOut])
def admin_postings(db: Session = Depends(get_db)) -> list[AdminPostingOut]:
    total, new = _counts(db)
    order = {"open": 0, "draft": 1, "closed": 2}
    rows = sorted(db.query(JobPosting).all(), key=lambda p: (order.get(p.status, 3), -p.id))
    return [_admin_out(p, total, new) for p in rows]


def _get_posting(db: Session, posting_id: int) -> JobPosting:
    posting = db.get(JobPosting, posting_id)
    if posting is None:
        raise HTTPException(404, "Posting not found")
    return posting


def _apply_fields(p: JobPosting, body: PostingIn) -> None:
    p.title, p.department, p.location = body.title.strip(), body.department.strip(), body.location.strip()
    p.workplace, p.employment_type, p.salary_range = body.workplace, body.employment_type, body.salary_range.strip()
    p.summary, p.description = body.summary.strip(), body.description.strip()
    p.responsibilities, p.requirements = _items(body.responsibilities), _items(body.requirements)
    p.nice_to_have, p.benefits = _items(body.nice_to_have), _items(body.benefits)
    if body.status == "open" and p.published_at is None:
        p.published_at = utcnow()
    p.status = body.status
    p.updated_at = utcnow()


@admin.get("/postings/{posting_id}", response_model=AdminPostingOut)
def admin_posting(posting_id: int, db: Session = Depends(get_db)) -> AdminPostingOut:
    return _admin_out(_get_posting(db, posting_id), *_counts(db))


@admin.post("/postings", response_model=AdminPostingOut, status_code=status.HTTP_201_CREATED)
def create_posting(body: PostingIn, db: Session = Depends(get_db)) -> AdminPostingOut:
    posting = JobPosting(slug=_slugify(db, body.title))
    _apply_fields(posting, body)
    db.add(posting)
    db.commit()
    return _admin_out(posting, *_counts(db))


@admin.put("/postings/{posting_id}", response_model=AdminPostingOut)
def update_posting(posting_id: int, body: PostingIn, db: Session = Depends(get_db)) -> AdminPostingOut:
    posting = _get_posting(db, posting_id)
    if posting.status == "draft" and body.title.strip() != posting.title:
        posting.slug = _slugify(db, body.title, posting.id)  # links only stay fixed once published
    _apply_fields(posting, body)
    db.commit()
    return _admin_out(posting, *_counts(db))


@admin.delete("/postings/{posting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_posting(posting_id: int, db: Session = Depends(get_db)) -> Response:
    posting = _get_posting(db, posting_id)
    paths = [a.resume_path for a in db.query(JobApplication).filter(JobApplication.posting_id == posting_id) if a.resume_path]
    db.query(JobApplication).filter(JobApplication.posting_id == posting_id).delete(synchronize_session=False)
    db.delete(posting)
    db.commit()
    for path in paths:
        (get_settings().data_dir / path).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin.get("/applications", response_model=list[ApplicationOut])
def admin_applications(posting_id: int | None = None, status_: str = Query("", alias="status"),
                       db: Session = Depends(get_db)) -> list[ApplicationOut]:
    query = db.query(JobApplication, JobPosting.title).join(JobPosting)
    if posting_id is not None:
        query = query.filter(JobApplication.posting_id == posting_id)
    if status_:
        query = query.filter(JobApplication.status == status_)
    return [_application_out(a, title) for a, title in query.order_by(JobApplication.id.desc()).limit(500)]


def _get_application(db: Session, application_id: int) -> JobApplication:
    application = db.get(JobApplication, application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    return application


@admin.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application(application_id: int, body: ApplicationPatch, db: Session = Depends(get_db)) -> ApplicationOut:
    application = _get_application(db, application_id)
    if body.status is not None:
        application.status = body.status
    if body.notes is not None:
        application.notes = body.notes
    db.commit()
    return _application_out(application, _get_posting(db, application.posting_id).title)


@admin.get("/applications/{application_id}/resume")
def download_resume(application_id: int, db: Session = Depends(get_db)) -> FileResponse:
    application = _get_application(db, application_id)
    data_dir = get_settings().data_dir.resolve()
    path = (data_dir / application.resume_path).resolve() if application.resume_path else None
    if path is None or not path.is_file() or data_dir not in path.parents:
        raise HTTPException(404, "This application has no CV")
    return FileResponse(path, filename=application.resume_filename or path.name,
                        media_type="application/octet-stream")


@admin.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, db: Session = Depends(get_db)) -> Response:
    application = _get_application(db, application_id)
    path = application.resume_path
    db.delete(application)
    db.commit()
    if path:
        (get_settings().data_dir / path).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
