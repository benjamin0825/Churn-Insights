"""Password hashing, JWT access tokens and the authenticated-user dependency."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user: User) -> tuple[str, datetime]:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.token_ttl_minutes)
    payload = {"sub": str(user.id), "org": user.organization_id, "exp": expires}
    return jwt.encode(payload, settings.resolved_secret(), algorithm=ALGORITHM), expires


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        payload = jwt.decode(credentials.credentials, get_settings().resolved_secret(), algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User no longer exists")
    check_access(user)
    return user


def check_access(user: User) -> None:
    """Disabled accounts and suspended workspaces are locked out; site admins keep access to their own account."""
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled")
    if user.organization.status != "active" and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This workspace has been suspended")


def require_owner(user: User = Depends(current_user)) -> User:
    if user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only organization owners can do this")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only site administrators can do this")
    return user
