from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


def register(db: Session, data: RegisterRequest) -> tuple[User, str]:
    email = data.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise conflict("Email already registered", details={"email": email})

    user = User(
        email=email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    return user, token


def login(db: Session, data: LoginRequest) -> str:
    email = data.email.lower()
    user = db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    # verify_password handles a missing user via a dummy compare-style return.
    if user is None or not verify_password(data.password, user.password_hash):
        raise unauthorized("Invalid email or password")

    return create_access_token(subject=str(user.id))
