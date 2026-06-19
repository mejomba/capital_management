"""Realized and unrealized P&L in IRR and USD, with optional grouping."""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.lot import Lot
from app.models.lot_consumption import LotConsumption
from app.services import valuation

GroupBy = str  # "class" | "account" | "asset"


def _sum_opt(values: list[Decimal | None]) -> Decimal | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _group_key(group_by: GroupBy | None, asset: Asset, account_id: uuid.UUID) -> str | None:
    if group_by == "class":
        return asset.asset_class.value
    if group_by == "account":
        return str(account_id)
    if group_by == "asset":
        return asset.symbol
    return None


def realized(
    db: Session,
    user_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
    group_by: GroupBy | None,
) -> tuple[dict, dict]:
    conds = [Lot.user_id == user_id]
    if date_from is not None:
        conds.append(
            LotConsumption.consumed_at >= datetime.combine(date_from, time.min, timezone.utc)
        )
    if date_to is not None:
        conds.append(
            LotConsumption.consumed_at
            < datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc)
        )

    rows = db.execute(
        select(LotConsumption, Lot, Asset)
        .join(Lot, LotConsumption.lot_id == Lot.id)
        .join(Asset, Asset.id == Lot.asset_id)
        .where(*conds)
    ).all()

    total = {"irr": [], "usd": []}
    groups: dict[str, dict] = {}
    for lc, lot, asset in rows:
        total["irr"].append(lc.realized_pnl_irr)
        total["usd"].append(lc.realized_pnl_usd)
        key = _group_key(group_by, asset, lot.account_id)
        if key is not None:
            g = groups.setdefault(key, {"irr": [], "usd": []})
            g["irr"].append(lc.realized_pnl_irr)
            g["usd"].append(lc.realized_pnl_usd)
    return total, groups


def unrealized(
    db: Session,
    user_id: uuid.UUID,
    as_of: date | datetime,
    group_by: GroupBy | None,
) -> tuple[dict, dict]:
    rows = db.execute(
        select(Lot, Asset)
        .join(Asset, Asset.id == Lot.asset_id)
        .where(Lot.user_id == user_id, Lot.remaining_qty != 0)
    ).all()

    mv_cache: dict[tuple[uuid.UUID, str], Decimal | None] = {}

    def mv(asset: Asset, ccy: str) -> Decimal | None:
        key = (asset.id, ccy)
        if key not in mv_cache:
            mv_cache[key] = valuation.market_unit_value(db, user_id, asset, ccy, as_of)
        return mv_cache[key]

    total = {"irr": [], "usd": []}
    groups: dict[str, dict] = {}
    for lot, asset in rows:
        for ccy, field in (("irr", "unit_cost_irr"), ("usd", "unit_cost_usd")):
            market = mv(asset, valuation.IRR if ccy == "irr" else valuation.USD)
            cost = getattr(lot, field)
            value = (
                (market - cost) * lot.remaining_qty
                if market is not None and cost is not None
                else None
            )
            total[ccy].append(value)
            key = _group_key(group_by, asset, lot.account_id)
            if key is not None:
                groups.setdefault(key, {"irr": [], "usd": []})[ccy].append(value)
    return total, groups


def pnl_report(
    db: Session,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    group_by: GroupBy | None = None,
) -> dict:
    r_total, r_groups = realized(db, user_id, date_from, date_to, group_by)
    as_of = date_to or datetime.now(timezone.utc).date()
    u_total, u_groups = unrealized(db, user_id, as_of, group_by)

    groups = []
    for key in sorted(set(r_groups) | set(u_groups)):
        rg = r_groups.get(key, {"irr": [], "usd": []})
        ug = u_groups.get(key, {"irr": [], "usd": []})
        groups.append(
            {
                "key": key,
                "realized_irr": _sum_opt(rg["irr"]),
                "realized_usd": _sum_opt(rg["usd"]),
                "unrealized_irr": _sum_opt(ug["irr"]),
                "unrealized_usd": _sum_opt(ug["usd"]),
            }
        )

    return {
        "realized": {"irr": _sum_opt(r_total["irr"]), "usd": _sum_opt(r_total["usd"])},
        "unrealized": {"irr": _sum_opt(u_total["irr"]), "usd": _sum_opt(u_total["usd"])},
        "group_by": group_by,
        "groups": groups,
    }
