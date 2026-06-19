"""Derived holdings — never stored. holding = Σ leg.quantity over active,
non-deleted transactions (CLAUDE.md golden rule, DATA_MODEL.md)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.lot import Lot
from app.models.transaction import Transaction, TransactionStatus
from app.models.transaction_leg import TransactionLeg
from app.services import valuation


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


# --- valuation (M3) --------------------------------------------------------

def _sum_opt(values: list[Decimal | None]) -> Decimal | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _open_lots_map(
    db: Session, user_id: uuid.UUID
) -> dict[tuple[uuid.UUID, uuid.UUID], list[Lot]]:
    grouped: dict[tuple[uuid.UUID, uuid.UUID], list[Lot]] = {}
    for lot in db.scalars(
        select(Lot).where(Lot.user_id == user_id, Lot.remaining_qty != 0)
    ):
        grouped.setdefault((lot.account_id, lot.asset_id), []).append(lot)
    return grouped


def _unrealized(lots: list[Lot], market_unit: Decimal | None, currency: str) -> Decimal | None:
    if market_unit is None:
        return None
    field = "unit_cost_irr" if currency == valuation.IRR else "unit_cost_usd"
    contribs = [
        (market_unit - getattr(lot, field)) * lot.remaining_qty
        for lot in lots
        if getattr(lot, field) is not None
    ]
    return sum(contribs) if contribs else None


def valued_holdings(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> list[dict]:
    eff = as_of or datetime.now(timezone.utc)
    lots_map = _open_lots_map(db, user_id)
    asset_cache: dict[uuid.UUID, Asset] = {}
    rows = []
    for h in holdings(db, user_id, as_of):
        asset = asset_cache.get(h["asset_id"]) or db.get(Asset, h["asset_id"])
        asset_cache[asset.id] = asset
        mv_irr = valuation.market_unit_value(db, user_id, asset, valuation.IRR, eff)
        mv_usd = valuation.market_unit_value(db, user_id, asset, valuation.USD, eff)
        lots = lots_map.get((h["account_id"], h["asset_id"]), [])
        rows.append(
            {
                **h,
                "value_irr": mv_irr * h["quantity"] if mv_irr is not None else None,
                "value_usd": mv_usd * h["quantity"] if mv_usd is not None else None,
                "unrealized_pnl_irr": _unrealized(lots, mv_irr, valuation.IRR),
                "unrealized_pnl_usd": _unrealized(lots, mv_usd, valuation.USD),
            }
        )
    return rows


def valued_by_asset(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> list[dict]:
    grouped: dict[uuid.UUID, list[dict]] = {}
    asset_cache: dict[uuid.UUID, Asset] = {}
    for row in valued_holdings(db, user_id, as_of):
        grouped.setdefault(row["asset_id"], []).append(row)
    out = []
    for asset_id, group in grouped.items():
        asset = asset_cache.get(asset_id) or db.get(Asset, asset_id)
        out.append(
            {
                "asset_id": asset_id,
                "symbol": group[0]["symbol"],
                "asset_class": asset.asset_class,
                "quantity": sum(r["quantity"] for r in group),
                "value_irr": _sum_opt([r["value_irr"] for r in group]),
                "value_usd": _sum_opt([r["value_usd"] for r in group]),
                "unrealized_pnl_irr": _sum_opt([r["unrealized_pnl_irr"] for r in group]),
                "unrealized_pnl_usd": _sum_opt([r["unrealized_pnl_usd"] for r in group]),
            }
        )
    out.sort(key=lambda r: r["symbol"])
    return out


def valued_by_class(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> list[dict]:
    grouped: dict = {}
    asset_cache: dict[uuid.UUID, Asset] = {}
    for row in valued_by_asset(db, user_id, as_of):
        asset = asset_cache.get(row["asset_id"]) or db.get(Asset, row["asset_id"])
        grouped.setdefault(asset.asset_class, []).append(row)
    return [{"asset_class": cls, "items": items} for cls, items in grouped.items()]
