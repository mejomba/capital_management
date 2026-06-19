import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import unprocessable
from app.core.pagination import PageParams
from app.models.asset import Asset
from app.models.price import Price
from app.schemas.price import PriceCreate
from app.services import valuation


def _assert_visible_asset(db: Session, user_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    visible = db.scalar(
        select(Asset.id).where(
            Asset.id == asset_id,
            Asset.deleted_at.is_(None),
            ((Asset.user_id == user_id) | (Asset.user_id.is_(None))),
        )
    )
    if visible is None:
        raise unprocessable(
            "Unknown or inaccessible asset", details={"asset_id": str(asset_id)}
        )


def list_prices(
    db: Session,
    user_id: uuid.UUID,
    params: PageParams,
    asset_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Price], int]:
    conds = [Price.user_id == user_id]
    if asset_id is not None:
        conds.append(Price.asset_id == asset_id)
    if date_from is not None:
        conds.append(Price.as_of >= date_from)
    if date_to is not None:
        conds.append(Price.as_of <= date_to)

    total = db.scalar(select(func.count()).select_from(Price).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Price)
            .where(*conds)
            .order_by(Price.as_of.desc(), Price.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return items, total


def create_price(db: Session, user_id: uuid.UUID, data: PriceCreate) -> Price:
    _assert_visible_asset(db, user_id, data.asset_id)
    price = Price(
        user_id=user_id,
        asset_id=data.asset_id,
        quote_currency=data.quote_currency,
        price=data.price,
        as_of=data.as_of,
        source=data.source,
    )
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


def create_prices_bulk(
    db: Session, user_id: uuid.UUID, items: list[PriceCreate]
) -> list[Price]:
    for item in items:
        _assert_visible_asset(db, user_id, item.asset_id)
    prices = [
        Price(
            user_id=user_id,
            asset_id=item.asset_id,
            quote_currency=item.quote_currency,
            price=item.price,
            as_of=item.as_of,
            source=item.source,
        )
        for item in items
    ]
    db.add_all(prices)
    db.commit()
    for price in prices:
        db.refresh(price)
    return prices


def fx_rate(
    db: Session, user_id: uuid.UUID, from_ccy: str, to_ccy: str, as_of: date
) -> Decimal | None:
    """Derived FX rate (value of 1 unit of from_ccy in to_ccy) from prices."""
    return valuation.convert(db, user_id, Decimal(1), from_ccy, to_ccy, as_of)
