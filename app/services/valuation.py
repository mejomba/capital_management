"""Pricing, FX, and currency conversion on the IRR/USD axis.

Rule (DATA_MODEL.md): convert with the nearest price whose as_of <= target
date. When a value cannot be resolved we return None (unvalued) — never raise.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetClass
from app.models.price import Price

IRR = "IRR"
USD = "USD"


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def nearest_price(
    db: Session,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    quote_currency: str,
    as_of: date | datetime,
) -> Decimal | None:
    return db.scalar(
        select(Price.price)
        .where(
            Price.user_id == user_id,
            Price.asset_id == asset_id,
            Price.quote_currency == quote_currency,
            Price.as_of <= _as_date(as_of),
        )
        .order_by(Price.as_of.desc())
        .limit(1)
    )


def resolve_currency_asset(
    db: Session, user_id: uuid.UUID, symbol: str
) -> Asset | None:
    """Asset whose symbol is a currency code, preferring the shared system one."""
    return db.scalar(
        select(Asset)
        .where(
            Asset.symbol == symbol,
            Asset.deleted_at.is_(None),
            ((Asset.user_id == user_id) | (Asset.user_id.is_(None))),
        )
        .order_by(Asset.user_id.is_(None).desc())
        .limit(1)
    )


def fx_usd_irr(db: Session, user_id: uuid.UUID, as_of: date | datetime) -> Decimal | None:
    usd = resolve_currency_asset(db, user_id, USD)
    if usd is None:
        return None
    return nearest_price(db, user_id, usd.id, IRR, as_of)


def _price_via_currency_asset(
    db: Session, user_id: uuid.UUID, ccy: str, target: str, as_of: date | datetime
) -> Decimal | None:
    """Unit value of one `ccy` expressed in `target` using ccy's own price rows."""
    asset = resolve_currency_asset(db, user_id, ccy)
    if asset is None:
        return None
    direct = nearest_price(db, user_id, asset.id, target, as_of)
    if direct is not None:
        return direct
    # bridge through the other reporting currency
    bridge = USD if target == IRR else IRR
    via = nearest_price(db, user_id, asset.id, bridge, as_of)
    if via is None:
        return None
    bridge_rate = _unit_rate(db, user_id, bridge, target, as_of)
    return via * bridge_rate if bridge_rate is not None else None


def _unit_rate(
    db: Session, user_id: uuid.UUID, from_ccy: str, to_ccy: str, as_of: date | datetime
) -> Decimal | None:
    """Value of 1 unit of from_ccy in to_ccy, restricted to the IRR/USD axis."""
    if from_ccy == to_ccy:
        return Decimal(1)
    fx = fx_usd_irr(db, user_id, as_of)
    if {from_ccy, to_ccy} == {USD, IRR} and fx is not None:
        return fx if (from_ccy == USD) else (Decimal(1) / fx)
    return None


def convert(
    db: Session,
    user_id: uuid.UUID,
    amount: Decimal | None,
    from_ccy: str,
    to_ccy: str,
    as_of,
) -> Decimal | None:
    return _convert(db, user_id, amount, from_ccy, to_ccy, as_of)


def to_irr(
    db: Session, user_id: uuid.UUID, amount: Decimal | None, ccy: str, as_of
) -> Decimal | None:
    return _convert(db, user_id, amount, ccy, IRR, as_of)


def to_usd(
    db: Session, user_id: uuid.UUID, amount: Decimal | None, ccy: str, as_of
) -> Decimal | None:
    return _convert(db, user_id, amount, ccy, USD, as_of)


def _convert(
    db: Session,
    user_id: uuid.UUID,
    amount: Decimal | None,
    ccy: str,
    target: str,
    as_of,
) -> Decimal | None:
    if amount is None:
        return None
    if ccy == target:
        return amount
    rate = _unit_rate(db, user_id, ccy, target, as_of)
    if rate is not None:
        return amount * rate
    # arbitrary fiat (e.g. EUR) via its own price rows
    unit = _price_via_currency_asset(db, user_id, ccy, target, as_of)
    return amount * unit if unit is not None else None


def _nearest_price_any(
    db: Session, user_id: uuid.UUID, asset: Asset, as_of
) -> tuple[Decimal, str] | None:
    """Most relevant price for a non-fiat asset, preferring its quote_currency."""
    preferred = nearest_price(db, user_id, asset.id, asset.quote_currency, as_of)
    if preferred is not None:
        return preferred, asset.quote_currency
    row = db.execute(
        select(Price.price, Price.quote_currency)
        .where(
            Price.user_id == user_id,
            Price.asset_id == asset.id,
            Price.as_of <= _as_date(as_of),
        )
        .order_by(Price.as_of.desc())
        .limit(1)
    ).first()
    return (row.price, row.quote_currency) if row else None


def market_unit_value(
    db: Session, user_id: uuid.UUID, asset: Asset, target: str, as_of
) -> Decimal | None:
    """Current value of one unit of `asset` in `target` (IRR or USD)."""
    if asset.asset_class is AssetClass.fiat:
        return _convert(db, user_id, Decimal(1), asset.symbol, target, as_of)
    found = _nearest_price_any(db, user_id, asset, as_of)
    if found is None:
        return None
    price, qccy = found
    return _convert(db, user_id, price, qccy, target, as_of)
