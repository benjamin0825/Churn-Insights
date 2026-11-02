"""Site administration: every organization, user, job and plan. Requires ``User.is_admin``.

Also serves the public plan list that the pricing page reads.
"""

from __future__ import annotations

import re
import secrets
import shutil
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import jobs
from ..db import get_db
from ..models import Campaign, Dataset, Job, Organization, Plan, User, utcnow
from ..security import hash_password, require_admin
from ..workspace import Workspace, org_lock
from .jobs import JobOut, job_out

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
public = APIRouter(prefix="/api", tags=["plans"])

PAGE_SIZE = 25
DEFAULT_PLAN = "starter"  # Organization.plan default for new sign-ups


def _page(query, page: int, size: int = PAGE_SIZE):
    total = query.order_by(None).count()
    return total, query.offset((page - 1) * size).limit(size).all()


def _like(text: str) -> str:
    return f"%{text.strip().lower()}%"


# ---------------------------------------------------------------- overview
@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    now = utcnow()
    since_30d = now - timedelta(days=30)
    weeks = 12
    start = (now - timedelta(weeks=weeks - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start -= timedelta(days=start.weekday())  # Monday of the first week
    signups = [0] * weeks
    for (created,) in db.query(Organization.created_at).filter(Organization.created_at >= start):
        index = (created - start).days // 7
        if 0 <= index < weeks:
            signups[index] += 1
    active_orgs = {org_id for (org_id,) in db.query(Job.organization_id).filter(Job.created_at >= since_30d)}
    active_orgs |= {org_id for (org_id,) in db.query(Dataset.organization_id).filter(Dataset.created_at >= since_30d)}
    by_status = dict(db.query(Job.status, func.count()).group_by(Job.status).all())
    plans = {p.key: p.name for p in db.query(Plan)}
    by_plan = [{"plan": key, "name": plans.get(key, key), "organizations": n}
               for key, n in db.query(Organization.plan, func.count()).group_by(Organization.plan).all()]
    failed = (db.query(Job).filter(Job.status == "failed", Job.created_at >= now - timedelta(days=7))
              .order_by(Job.id.desc()).limit(5).all())
    org_names = dict(db.query(Organization.id, Organization.name))
    return {
        "organizations": db.query(Organization).count(),
        "suspended": db.query(Organization).filter(Organization.status != "active").count(),
        "users": db.query(User).count(),
        "admins": db.query(User).filter(User.is_admin.is_(True)).count(),
        "active_organizations_30d": len(active_orgs),
        "new_organizations_30d": db.query(Organization).filter(Organization.created_at >= since_30d).count(),
        "jobs": {"queued": by_status.get("queued", 0), "running": by_status.get("running", 0),
                 "failed_7d": db.query(Job).filter(Job.status == "failed", Job.created_at >= now - timedelta(days=7)).count(),
                 "total": sum(by_status.values())},
        "signups_by_week": [{"week_start": (start + timedelta(weeks=i)).date().isoformat(), "organizations": n}
                            for i, n in enumerate(signups)],
        "by_plan": sorted(by_plan, key=lambda r: -r["organizations"]),
        "recent_failures": [{**_job_row(j, org_names)} for j in failed],
    }


# ----------------------------------------------------------- organizations
class OrgPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    plan: str | None = None
    status: Literal["active", "suspended"] | None = None


def _org_row(org: Organization, db: Session, users: int, owner: str | None) -> dict:
    ws = Workspace(org.id)
    dataset = (db.query(Dataset).filter(Dataset.organization_id == org.id).order_by(Dataset.id.desc()).first())
    last_job = db.query(func.max(Job.created_at)).filter(Job.organization_id == org.id).scalar()
    activity = [t for t in (last_job, dataset.created_at if dataset else None) if t is not None]
    return {
        "id": org.id, "name": org.name, "plan": org.plan, "status": org.status,
        "created_at": org.created_at.isoformat(), "users": users, "owner_email": owner,
        "customers": (dataset.summary or {}).get("customers") if dataset else None,
        "data_source": dataset.source if dataset else None,
        "model_version": ws.production_version(),
        "last_activity": max(activity).isoformat() if activity else None,
    }


@router.get("/organizations")
def list_organizations(q: str = "", plan: str = "", status_: str = Query("", alias="status"),
                       page: int = Query(1, ge=1), db: Session = Depends(get_db)) -> dict:
    query = db.query(Organization)
    if q.strip():
        members = db.query(User.organization_id).filter(func.lower(User.email).like(_like(q)))
        query = query.filter(or_(func.lower(Organization.name).like(_like(q)), Organization.id.in_(members)))
    if plan:
        query = query.filter(Organization.plan == plan)
    if status_:
        query = query.filter(Organization.status == status_)
    total, rows = _page(query.order_by(Organization.id.desc()), page)
    ids = [o.id for o in rows]
    counts = dict(db.query(User.organization_id, func.count()).filter(User.organization_id.in_(ids))
                  .group_by(User.organization_id))
    owners: dict[int, str] = {}
    for org_id, email in (db.query(User.organization_id, User.email).filter(User.organization_id.in_(ids),
                                                                            User.role == "owner").order_by(User.id)):
        owners.setdefault(org_id, email)
    return {"total": total, "page": page, "page_size": PAGE_SIZE,
            "items": [_org_row(o, db, counts.get(o.id, 0), owners.get(o.id)) for o in rows]}


def _get_org(db: Session, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(404, "Organization not found")
    return org


@router.get("/organizations/{org_id}")
def organization_detail(org_id: int, db: Session = Depends(get_db)) -> dict:
    org = _get_org(db, org_id)
    users = db.query(User).filter(User.organization_id == org_id).order_by(User.id).all()
    owner = next((u.email for u in users if u.role == "owner"), None)
    recent = db.query(Job).filter(Job.organization_id == org_id).order_by(Job.id.desc()).limit(10).all()
    datasets = db.query(Dataset).filter(Dataset.organization_id == org_id).order_by(Dataset.id.desc()).limit(5).all()
    return {
        **_org_row(org, db, len(users), owner),
        "users_list": [_user_row(u, org.name) for u in users],
        "jobs": [job_out(j).model_dump(mode="json") for j in recent],
        "datasets": [{"id": d.id, "source": d.source, "created_at": d.created_at.isoformat(), "summary": d.summary}
                     for d in datasets],
        "campaigns": db.query(Campaign).filter(Campaign.organization_id == org_id).count(),
        "economics": {"offer_cost": org.offer_cost, "retention_success_rate": org.retention_success_rate,
                      "months_of_value": org.months_of_value},
    }


@router.patch("/organizations/{org_id}")
def update_organization(org_id: int, body: OrgPatch, admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict:
    org = _get_org(db, org_id)
    if body.plan is not None:
        if db.get(Plan, body.plan) is None:
            raise HTTPException(422, f"Unknown plan {body.plan!r}")
        org.plan = body.plan
    if body.status is not None:
        if body.status != "active" and org.id == admin.organization_id:
            raise HTTPException(409, "You can't suspend your own workspace")
        org.status = body.status
    if body.name is not None:
        org.name = body.name.strip()
    db.commit()
    return organization_detail(org_id, db)


@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(org_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    org = _get_org(db, org_id)
    if org.id == admin.organization_id:
        raise HTTPException(409, "You can't delete your own workspace")
    if jobs.active_job(db, org_id, jobs.JOB_KINDS) is not None or org_lock(org_id).locked():
        raise HTTPException(409, "A job is running for this workspace; wait for it or mark it failed first")
    # Bulk delete so SQLite's ON DELETE CASCADE removes users, jobs, datasets and campaigns.
    db.query(Organization).filter(Organization.id == org_id).delete(synchronize_session=False)
    db.commit()
    shutil.rmtree(Workspace(org_id).root, ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------- users
class UserPatch(BaseModel):
    role: Literal["owner", "analyst"] | None = None
    is_active: bool | None = None
    is_admin: bool | None = None
    name: str | None = Field(None, min_length=1, max_length=200)


def _user_row(user: User, org_name: str | None = None) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_admin": user.is_admin,
            "is_active": user.is_active, "created_at": user.created_at.isoformat(),
            "organization_id": user.organization_id, "organization_name": org_name or user.organization.name}


@router.get("/users")
def list_users(q: str = "", page: int = Query(1, ge=1), admins_only: bool = False,
               db: Session = Depends(get_db)) -> dict:
    query = db.query(User).join(Organization)
    if q.strip():
        query = query.filter(or_(func.lower(User.email).like(_like(q)), func.lower(User.name).like(_like(q)),
                                 func.lower(Organization.name).like(_like(q))))
    if admins_only:
        query = query.filter(User.is_admin.is_(True))
    total, rows = _page(query.order_by(User.id.desc()), page)
    return {"total": total, "page": page, "page_size": PAGE_SIZE, "items": [_user_row(u) for u in rows]}


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    user = _get_user(db, user_id)
    if user.id == admin.id and (body.is_admin is False or body.is_active is False):
        raise HTTPException(409, "You can't remove your own admin access or disable your own account")
    if body.role == "analyst" and user.role == "owner":
        owners = db.query(User).filter(User.organization_id == user.organization_id, User.role == "owner").count()
        if owners <= 1:
            raise HTTPException(409, "A workspace needs at least one owner; make someone else owner first")
    for field in ("role", "is_active", "is_admin"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    if body.name is not None:
        user.name = body.name.strip()
    db.commit()
    return _user_row(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_db)) -> dict:
    """Sets a random temporary password and returns it once, for the admin to pass on."""
    user = _get_user(db, user_id)
    temporary = "-".join(secrets.token_urlsafe(4) for _ in range(3))
    user.password_hash = hash_password(temporary)
    db.commit()
    return {"email": user.email, "temporary_password": temporary}


# -------------------------------------------------------------------- jobs
def _job_row(job: Job, org_names: dict[int, str]) -> dict:
    return {**job_out(job).model_dump(mode="json"), "organization_id": job.organization_id,
            "organization_name": org_names.get(job.organization_id)}


@router.get("/jobs")
def list_jobs(status_: str = Query("", alias="status"), kind: str = "", organization_id: int | None = None,
              page: int = Query(1, ge=1), db: Session = Depends(get_db)) -> dict:
    query = db.query(Job)
    if status_:
        query = query.filter(Job.status == status_)
    if kind:
        query = query.filter(Job.kind == kind)
    if organization_id is not None:
        query = query.filter(Job.organization_id == organization_id)
    total, rows = _page(query.order_by(Job.id.desc()), page)
    names = dict(db.query(Organization.id, Organization.name).filter(Organization.id.in_({j.organization_id for j in rows})))
    return {"total": total, "page": page, "page_size": PAGE_SIZE, "items": [_job_row(j, names) for j in rows]}


@router.post("/jobs/{job_id}/fail", response_model=JobOut)
def mark_job_failed(job_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> JobOut:
    """Clears a job left 'queued' or 'running' (for example after a server restart) so the workspace is unblocked."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(409, f"Job is already {job.status}")
    job.status, job.message, job.finished_at = "failed", "marked failed by an administrator", utcnow()
    job.error = f"Marked failed by administrator {admin.email} at {datetime.now().isoformat(timespec='seconds')}"
    db.commit()
    return job_out(job)


# ------------------------------------------------------------------- plans
class PlanIn(BaseModel):
    key: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=80)
    monthly_price: float = Field(ge=0, le=1_000_000)
    blurb: str = Field("", max_length=300)
    limits: list[str] = Field(default_factory=list, max_length=6)
    features: list[str] = Field(default_factory=list, max_length=30)
    popular: bool = False
    active: bool = True
    sort_order: int = 0


class PlanOut(PlanIn):
    organizations: int = 0


def _clean_list(items: list[str]) -> list[str]:
    return [re.sub(r"\s+", " ", i).strip()[:200] for i in items if i.strip()]


def _plan_out(plan: Plan, counts: dict[str, int]) -> PlanOut:
    return PlanOut(key=plan.key, name=plan.name, monthly_price=plan.monthly_price, blurb=plan.blurb,
                   limits=plan.limits or [], features=plan.features or [], popular=plan.popular, active=plan.active,
                   sort_order=plan.sort_order, organizations=counts.get(plan.key, 0))


def _plan_counts(db: Session) -> dict[str, int]:
    return dict(db.query(Organization.plan, func.count()).group_by(Organization.plan).all())


@router.get("/plans", response_model=list[PlanOut])
def admin_plans(db: Session = Depends(get_db)) -> list[PlanOut]:
    counts = _plan_counts(db)
    return [_plan_out(p, counts) for p in db.query(Plan).order_by(Plan.sort_order, Plan.key)]


def _apply(plan: Plan, body: PlanIn, db: Session) -> None:
    plan.name, plan.monthly_price, plan.blurb = body.name.strip(), body.monthly_price, body.blurb.strip()
    plan.limits, plan.features = _clean_list(body.limits), _clean_list(body.features)
    plan.active, plan.sort_order, plan.popular = body.active, body.sort_order, body.popular
    if body.popular:  # only one plan carries the "Popular" badge
        db.query(Plan).filter(Plan.key != plan.key).update({Plan.popular: False})


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanIn, db: Session = Depends(get_db)) -> PlanOut:
    if db.get(Plan, body.key) is not None:
        raise HTTPException(409, f"A plan with key {body.key!r} already exists")
    plan = Plan(key=body.key)
    db.add(plan)
    _apply(plan, body, db)
    db.commit()
    return _plan_out(plan, _plan_counts(db))


@router.put("/plans/{key}", response_model=PlanOut)
def update_plan(key: str, body: PlanIn, db: Session = Depends(get_db)) -> PlanOut:
    plan = db.get(Plan, key)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    if body.key != key:
        raise HTTPException(422, "A plan's key can't be changed")
    _apply(plan, body, db)
    db.commit()
    return _plan_out(plan, _plan_counts(db))


@router.delete("/plans/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(key: str, db: Session = Depends(get_db)) -> Response:
    plan = db.get(Plan, key)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    if key == DEFAULT_PLAN:
        raise HTTPException(409, "New sign-ups start on this plan, so it can't be deleted; hide it instead")
    in_use = db.query(Organization).filter(Organization.plan == key).count()
    if in_use:
        raise HTTPException(409, f"{in_use} workspace(s) are on this plan; move them to another plan first")
    db.delete(plan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public.get("/plans", response_model=list[PlanIn])
def public_plans(db: Session = Depends(get_db)) -> list[PlanIn]:
    """Active plans for the public pricing page (no login needed)."""
    rows = db.query(Plan).filter(Plan.active.is_(True)).order_by(Plan.sort_order, Plan.key)
    return [PlanIn.model_validate(_plan_out(p, {}).model_dump(exclude={"organizations"})) for p in rows]
