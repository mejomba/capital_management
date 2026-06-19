"""Shared dependencies: current-user extraction from JWT + ownership guard."""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import forbidden, unauthorized
from app.core.security import decode_access_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise unauthorized("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise unauthorized("Token expired")
    except jwt.PyJWTError:
        raise unauthorized("Invalid token")

    sub = payload.get("sub")
    if not sub:
        raise unauthorized("Invalid token payload")

    try:
        user_id = uuid.UUID(str(sub))
    except ValueError:
        raise unauthorized("Invalid token subject")

    user = db.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user is None:
        raise unauthorized("User no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def ensure_owner(resource_user_id: uuid.UUID, current_user: User) -> None:
    """Raise 403 if the resource is not owned by the current user."""
    if resource_user_id != current_user.id:
        raise forbidden("You do not have access to this resource")
