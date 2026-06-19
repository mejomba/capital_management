"""Derived holdings — never stored. holding = Σ leg.quantity over active,
non-deleted transactions (CLAUDE.md golden rule, DATA_MODEL.md)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.transaction import Transaction, TransactionStatus
from app.models.transaction_leg import TransactionLeg


def _active_legs_query(user_id: uuid.UUID, as_of: datetime | None):
    """Base query joining legs to their (active, non-deleted) transactions."""
    q = (
        select(TransactionLeg)
        .join(Transaction, TransactionLeg.transaction_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.active,
            Transaction.deleted_at.is_(None),
        )
    )
    if as_of is not None:
        q = q.where(Transaction.occurred_at <= as_of)
    return q


def holdings(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> list[dict]:
    base = _active_legs_query(user_id, as_of).subquery()
    stmt = (
        select(
            base.c.account_id,
            base.c.asset_id,
            Asset.symbol,
            func.sum(base.c.quantity).label("quantity"),
        )
        .join(Asset, Asset.id == base.c.asset_id)
        .group_by(base.c.account_id, base.c.asset_id, Asset.symbol)
        .having(func.sum(base.c.quantity) != 0)
        .order_by(Asset.symbol)
    )
    return [
        {
            "account_id": r.account_id,
            "asset_id": r.asset_id,
            "symbol": r.symbol,
            "quantity": r.quantity,
        }
        for r in db.execute(stmt)
    ]


def holdings_by_asset(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> list[dict]:
    base = _active_legs_query(user_id, as_of).subquery()
    stmt = (
        select(
            base.c.asset_id,
            Asset.symbol,
            Asset.asset_class,
            func.sum(base.c.quantity).label("quantity"),
        )
        .join(Asset, Asset.id == base.c.asset_id)
        .group_by(base.c.asset_id, Asset.symbol, Asset.asset_class)
        .having(func.sum(base.c.quantity) != 0)
        .order_by(Asset.symbol)
    )
    return [
        {
            "asset_id": r.asset_id,
            "symbol": r.symbol,
            "asset_class": r.asset_class,
            "quantity": r.quantity,
        }
        for r in db.execute(stmt)
    ]


def holdings_by_class(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> list[dict]:
    grouped: dict = {}
    for row in holdings_by_asset(db, user_id, as_of):
        cls = row["asset_class"]
        grouped.setdefault(cls, []).append(
            {
                "asset_id": row["asset_id"],
                "symbol": row["symbol"],
                "quantity": row["quantity"],
            }
        )
    return [
        {"asset_class": cls, "items": items} for cls, items in grouped.items()
    ]


def holding_for_pairs(
    db: Session,
    user_id: uuid.UUID,
    pairs: set[tuple[uuid.UUID, uuid.UUID]],
) -> dict[tuple[uuid.UUID, uuid.UUID], Decimal]:
    """Current holding for a specific set of (account_id, asset_id) pairs.

    Used for the non-negative balance check. Reflects pending flushed changes in
    the current session transaction.
    """
    if not pairs:
        return {}
    base = _active_legs_query(user_id, as_of=None).subquery()
    stmt = select(
        base.c.account_id,
        base.c.asset_id,
        func.sum(base.c.quantity).label("quantity"),
    ).group_by(base.c.account_id, base.c.asset_id)

    result: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {p: Decimal(0) for p in pairs}
    for r in db.execute(stmt):
        key = (r.account_id, r.asset_id)
        if key in result:
            result[key] = r.quantity
    return result
