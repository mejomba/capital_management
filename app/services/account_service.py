import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.core.pagination import PageParams
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


def _owned(user_id: uuid.UUID):
    return (Account.user_id == user_id, Account.deleted_at.is_(None))


def list_accounts(
    db: Session, user_id: uuid.UUID, params: PageParams
) -> tuple[list[Account], int]:
    conds = _owned(user_id)
    total = db.scalar(select(func.count()).select_from(Account).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Account)
            .where(*conds)
            .order_by(Account.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return items, total


def get_account(db: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    account = db.scalar(
        select(Account).where(Account.id == account_id, *_owned(user_id))
    )
    if account is None:
        raise not_found("Account not found")
    return account


def create_account(db: Session, user_id: uuid.UUID, data: AccountCreate) -> Account:
    account = Account(
        user_id=user_id,
        name=data.name,
        type=data.type,
        currency_hint=data.currency_hint,
        note=data.note,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(
    db: Session, user_id: uuid.UUID, account_id: uuid.UUID, data: AccountUpdate
) -> Account:
    account = get_account(db, user_id, account_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
    account = get_account(db, user_id, account_id)
    account.deleted_at = datetime.now(timezone.utc)
    db.commit()
