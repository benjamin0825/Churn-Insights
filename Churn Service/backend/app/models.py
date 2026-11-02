"""ORM tables. Every tenant-owned row carries ``organization_id``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime as _DateTime
from sqlalchemy.types import TypeDecorator

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DateTime(TypeDecorator):
    """Timezone-aware UTC datetimes. SQLite drops tzinfo on storage; re-attach UTC on load,
    so the API always sends '+00:00' and browsers convert to local time correctly."""

    impl = _DateTime
    cache_ok = True

    def __init__(self, timezone: bool = True):  # noqa: ARG002 - signature kept for readability
        super().__init__(timezone=True)

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Business economics used by default in campaigns
    offer_cost: Mapped[float] = mapped_column(default=15.0)
    retention_success_rate: Mapped[float] = mapped_column(default=0.35)
    months_of_value: Mapped[float] = mapped_column(default=12.0)
    plan: Mapped[str] = mapped_column(String(40), default="starter")  # Plan.key
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | suspended

    users: Mapped[list[User]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="owner")  # owner | analyst
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # site operator; never set by sign-up
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="users")


class Dataset(Base):
    """One loaded set of raw tables (uploaded or demo). The newest one is active."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # upload | demo
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)


class Job(Base):
    """Background work: demo data generation, training, scoring, monitoring."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # demo | train | score | monitor
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | succeeded | failed
    message: Mapped[str] = mapped_column(String(500), default="")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    model_version: Mapped[int] = mapped_column(Integer)
    as_of_week: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Plan(Base):
    """A pricing plan shown on the public pricing page and assigned to organizations."""

    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    monthly_price: Mapped[float] = mapped_column(default=0.0)
    blurb: Mapped[str] = mapped_column(String(300), default="")
    limits: Mapped[list[str]] = mapped_column(JSON, default=list)
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    popular: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # shown on the pricing page
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class JobPosting(Base):
    """An open position on the public careers page. Not to be confused with ``Job`` (background work)."""

    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(80), default="Engineering")
    location: Mapped[str] = mapped_column(String(120), default="Remote")
    workplace: Mapped[str] = mapped_column(String(20), default="remote")  # remote | hybrid | onsite
    employment_type: Mapped[str] = mapped_column(String(20), default="full_time")  # full_time | part_time | contract
    salary_range: Mapped[str] = mapped_column(String(120), default="")
    summary: Mapped[str] = mapped_column(String(400), default="")
    description: Mapped[str] = mapped_column(Text, default="")  # plain text; blank lines separate paragraphs
    responsibilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    nice_to_have: Mapped[list[str]] = mapped_column(JSON, default=list)
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(50), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    portfolio_url: Mapped[str] = mapped_column(String(500), default="")  # GitHub, website, ...
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    resume_filename: Mapped[str] = mapped_column(String(200), default="")  # original name, for download
    resume_path: Mapped[str] = mapped_column(String(300), default="")  # relative to data_dir
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | reviewing | interview | offer | hired | rejected
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyProfile(Base):
    """The public About page's company text. A single row (id = 1), edited in the admin panel."""

    __tablename__ = "company_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    headline: Mapped[str] = mapped_column(String(160), default="")
    intro: Mapped[str] = mapped_column(Text, default="")
    mission: Mapped[str] = mapped_column(Text, default="")
    story: Mapped[str] = mapped_column(Text, default="")  # blank lines separate paragraphs
    founded: Mapped[str] = mapped_column(String(40), default="")
    headquarters: Mapped[str] = mapped_column(String(120), default="")
    contact_email: Mapped[str] = mapped_column(String(320), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    github_url: Mapped[str] = mapped_column(String(500), default="")
    values: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)  # [{title, text}]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TeamMember(Base):
    """A person shown on the About page."""

    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120))  # e.g. "CEO", "Senior ML Engineer"
    team: Mapped[str] = mapped_column(String(20), default="engineering")  # see routers.about.Team
    bio: Mapped[str] = mapped_column(Text, default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    github_url: Mapped[str] = mapped_column(String(500), default="")
    photo_path: Mapped[str] = mapped_column(String(300), default="")  # relative to data_dir
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
