"""About page: company profile and team members. Public read, admin write.

Member photos are stored under ``data_dir/team`` with random names and served publicly,
since they are meant for the public About page.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import CompanyProfile, TeamMember, utcnow
from ..security import require_admin

public = APIRouter(prefix="/api/about", tags=["about"])
admin = APIRouter(prefix="/api/admin/about", tags=["admin"], dependencies=[Depends(require_admin)])

Team = Literal["leadership", "ai", "backend", "frontend", "engineering", "product", "people", "finance", "operations"]
TEAM_ORDER = {"leadership": 0, "ai": 1, "backend": 2, "frontend": 3, "engineering": 4, "product": 5, "people": 6, "finance": 7,
              "operations": 8}
MAX_PHOTO_BYTES = 3 * 1024 * 1024
PHOTO_TYPES = {".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG",), ".webp": (b"RIFF",)}
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

# Starting text for a new install; everything here is edited in Admin → About page.
DEFAULT_PROFILE = {
    "headline": "We help subscription businesses keep their customers",
    "intro": "WSL Technologies builds Churn Insights: churn prediction and retention planning that teams act on every week.",
    "mission": "Make customer retention measurable, explainable and profitable for every subscription business.",
    "story": (
        "Subscription businesses lose customers quietly. Usage drops, support tickets pile up, payments slip, and by the "
        "time it shows up in revenue it is too late to act.\n\n"
        "We built Churn Insights so teams can see churn coming. It predicts who is likely to leave in the next 8 weeks, "
        "explains why, and plans retention offers that are worth more than they cost."
    ),
    "values": [
        {"title": "Customers first", "text": "We measure our work by the customers our users keep."},
        {"title": "Explain everything", "text": "A prediction without a reason is not useful. We show our work."},
        {"title": "Ship and learn", "text": "Small steps, real feedback, steady improvement."},
        {"title": "Own the outcome", "text": "Everyone owns their work from idea to production."},
    ],
}


# ------------------------------------------------------------------ schemas
class Value(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    text: str = Field("", max_length=300)


def _web(value: str) -> str:
    value = value.strip()
    if value and not re.match(r"^https?://", value, re.I):
        value = f"https://{value}"
    if value and not re.match(r"^https?://[^\s/$.?#][^\s]*$", value, re.I):
        raise HTTPException(422, f"{value!r} is not a web address")
    return value


def _email(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        return TypeAdapter(EmailStr).validate_python(value).lower()
    except ValidationError:
        raise HTTPException(422, f"{value!r} is not a valid email address") from None


class ProfileIn(BaseModel):
    headline: str = Field("", max_length=160)
    intro: str = Field("", max_length=600)
    mission: str = Field("", max_length=600)
    story: str = Field("", max_length=8000)
    founded: str = Field("", max_length=40)
    headquarters: str = Field("", max_length=120)
    contact_email: str = Field("", max_length=320)
    linkedin_url: str = Field("", max_length=500)
    github_url: str = Field("", max_length=500)
    values: list[Value] = Field(default_factory=list, max_length=8)


class ProfileOut(ProfileIn):
    updated_at: datetime | None = None


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    team: Team = "engineering"
    bio: str = Field("", max_length=1000)
    linkedin_url: str = Field("", max_length=500)
    github_url: str = Field("", max_length=500)
    visible: bool = True


class MemberOut(MemberIn):
    id: int
    photo_url: str | None
    sort_order: int


class OrderIn(BaseModel):
    ids: list[int] = Field(max_length=500)


# ------------------------------------------------------------------ helpers
def _profile(db: Session) -> CompanyProfile:
    profile = db.get(CompanyProfile, 1)
    if profile is None:
        profile = CompanyProfile(id=1, **DEFAULT_PROFILE)
        db.add(profile)
        db.commit()
    return profile


def _profile_out(p: CompanyProfile) -> ProfileOut:
    return ProfileOut(headline=p.headline, intro=p.intro, mission=p.mission, story=p.story, founded=p.founded,
                      headquarters=p.headquarters, contact_email=p.contact_email, linkedin_url=p.linkedin_url,
                      github_url=p.github_url, values=[Value(**v) for v in p.values or []], updated_at=p.updated_at)


def _member_out(m: TeamMember) -> MemberOut:
    # The photo URL changes when the photo does, so browsers never show a stale one.
    photo = f"/api/about/photos/{m.id}?v={Path(m.photo_path).stem[:8]}" if m.photo_path else None
    return MemberOut(id=m.id, name=m.name, title=m.title, team=m.team, bio=m.bio, linkedin_url=m.linkedin_url,
                     github_url=m.github_url, visible=m.visible, photo_url=photo, sort_order=m.sort_order)


def _ordered(rows: list[TeamMember]) -> list[TeamMember]:
    return sorted(rows, key=lambda m: (TEAM_ORDER.get(m.team, 9), m.sort_order, m.id))


def _get_member(db: Session, member_id: int) -> TeamMember:
    member = db.get(TeamMember, member_id)
    if member is None:
        raise HTTPException(404, "Team member not found")
    return member


def _remove_photo(member: TeamMember) -> None:
    if member.photo_path:
        (get_settings().data_dir / member.photo_path).unlink(missing_ok=True)
        member.photo_path = ""


# ------------------------------------------------------------------ public
@public.get("")
def about(db: Session = Depends(get_db)) -> dict:
    members = db.query(TeamMember).filter(TeamMember.visible.is_(True)).all()
    return {"profile": _profile_out(_profile(db)).model_dump(mode="json"),
            "members": [_member_out(m).model_dump() for m in _ordered(members)]}


@public.get("/photos/{member_id}")
def photo(member_id: int, db: Session = Depends(get_db)) -> FileResponse:
    member = db.get(TeamMember, member_id)
    data_dir = get_settings().data_dir.resolve()
    path = (data_dir / member.photo_path).resolve() if member and member.photo_path and member.visible else None
    if path is None or not path.is_file() or data_dir not in path.parents:
        raise HTTPException(404, "No photo")
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
                        headers={"Cache-Control": "public, max-age=86400"})


# ------------------------------------------------------------------ admin
@admin.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)) -> ProfileOut:
    return _profile_out(_profile(db))


@admin.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    p = _profile(db)
    p.headline, p.intro, p.mission, p.story = body.headline.strip(), body.intro.strip(), body.mission.strip(), body.story.strip()
    p.founded, p.headquarters = body.founded.strip(), body.headquarters.strip()
    p.contact_email = _email(body.contact_email)
    p.linkedin_url, p.github_url = _web(body.linkedin_url), _web(body.github_url)
    p.values = [{"title": v.title.strip(), "text": v.text.strip()} for v in body.values if v.title.strip()]
    p.updated_at = utcnow()
    db.commit()
    return _profile_out(p)


@admin.get("/members", response_model=list[MemberOut])
def list_members(db: Session = Depends(get_db)) -> list[MemberOut]:
    return [_member_out(m) for m in _ordered(db.query(TeamMember).all())]


def _apply(m: TeamMember, body: MemberIn) -> None:
    m.name, m.title, m.team, m.bio = body.name.strip(), body.title.strip(), body.team, body.bio.strip()
    m.linkedin_url, m.github_url, m.visible = _web(body.linkedin_url), _web(body.github_url), body.visible


@admin.post("/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def create_member(body: MemberIn, db: Session = Depends(get_db)) -> MemberOut:
    last = max((m.sort_order for m in db.query(TeamMember).filter(TeamMember.team == body.team)), default=-1)
    member = TeamMember(sort_order=last + 1)
    _apply(member, body)
    db.add(member)
    db.commit()
    return _member_out(member)


@admin.put("/members/order", response_model=list[MemberOut])
def reorder(body: OrderIn, db: Session = Depends(get_db)) -> list[MemberOut]:
    """Sets the display order within each team from the given list of ids."""
    members = {m.id: m for m in db.query(TeamMember).all()}
    for position, member_id in enumerate(body.ids):
        if member_id in members:
            members[member_id].sort_order = position
    db.commit()
    return [_member_out(m) for m in _ordered(list(members.values()))]


@admin.put("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: int, body: MemberIn, db: Session = Depends(get_db)) -> MemberOut:
    member = _get_member(db, member_id)
    _apply(member, body)
    db.commit()
    return _member_out(member)


@admin.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int, db: Session = Depends(get_db)) -> Response:
    member = _get_member(db, member_id)
    _remove_photo(member)
    db.delete(member)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin.post("/members/{member_id}/photo", response_model=MemberOut)
async def upload_photo(member_id: int, photo: UploadFile = File(...), db: Session = Depends(get_db)) -> MemberOut:
    member = _get_member(db, member_id)
    suffix = Path(photo.filename or "").suffix.lower()
    if suffix not in PHOTO_TYPES:
        raise HTTPException(422, "The photo must be a JPG, PNG or WebP image")
    content = await photo.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The photo must be 3 MB or smaller")
    if not content.startswith(PHOTO_TYPES[suffix]) or (suffix == ".webp" and content[8:12] != b"WEBP"):
        raise HTTPException(422, f"That file doesn't look like a {suffix} image")
    _remove_photo(member)
    relative = Path("team") / f"{secrets.token_hex(12)}{'.jpg' if suffix == '.jpeg' else suffix}"
    target = get_settings().data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    member.photo_path = relative.as_posix()
    db.commit()
    return _member_out(member)


@admin.delete("/members/{member_id}/photo", response_model=MemberOut)
def delete_photo(member_id: int, db: Session = Depends(get_db)) -> MemberOut:
    member = _get_member(db, member_id)
    _remove_photo(member)
    db.commit()
    return _member_out(member)
