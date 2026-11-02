"""Registration, login and the current user / organization."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Organization, User
from ..security import check_access, create_access_token, current_user, hash_password, require_owner, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class RegisterIn(BaseModel):
    organization: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class OrganizationOut(BaseModel):
    id: int
    name: str
    offer_cost: float
    retention_success_rate: float
    months_of_value: float


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_admin: bool
    organization: OrganizationOut


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class EconomicsIn(BaseModel):
    offer_cost: float = Field(ge=0, le=100000)
    retention_success_rate: float = Field(ge=0, le=1)
    months_of_value: float = Field(gt=0, le=120)


def user_out(user: User) -> UserOut:
    org = user.organization
    return UserOut(id=user.id, name=user.name, email=user.email, role=user.role, is_admin=user.is_admin,
                   organization=OrganizationOut(id=org.id, name=org.name, offer_cost=org.offer_cost,
                                                retention_success_rate=org.retention_success_rate,
                                                months_of_value=org.months_of_value))


def _token(user: User) -> TokenOut:
    token, expires = create_access_token(user)
    return TokenOut(access_token=token, expires_at=expires, user=user_out(user))


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    org = Organization(name=body.organization.strip())
    user = User(organization=org, email=email, name=body.name.strip(), password_hash=hash_password(body.password),
                role="owner")
    db.add_all([org, user])
    db.commit()
    db.refresh(user)
    return _token(user)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    check_access(user)
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return user_out(user)


@router.put("/organization/economics", response_model=OrganizationOut)
def update_economics(body: EconomicsIn, user: User = Depends(require_owner), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id)
    org.offer_cost, org.retention_success_rate, org.months_of_value = (
        body.offer_cost, body.retention_success_rate, body.months_of_value)
    db.commit()
    return user_out(user).organization
