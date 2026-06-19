import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.core.pagination import PageParams
from app.models.asset import Asset, AssetClass
from app.schemas.asset import AssetCreate, AssetUpdate


def _visible(user_id: uuid.UUID):
    """System assets (user_id IS NULL) plus the user's own assets."""
    return (
        or_(Asset.user_id == user_id, Asset.user_id.is_(None)),
        Asset.deleted_at.is_(None),
    )


def list_assets(
    db: Session,
    user_id: uuid.UUID,
    params: PageParams,
    asset_class: AssetClass | None = None,
    q: str | None = None,
) -> tuple[list[Asset], int]:
    conds = list(_visible(user_id))
    if asset_class is not None:
        conds.append(Asset.asset_class == asset_class)
    if q:
        like = f"%{q}%"
        conds.append(or_(Asset.symbol.ilike(like), Asset.name.ilike(like)))

    total = db.scalar(select(func.count()).select_from(Asset).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Asset)
            .where(*conds)
            # system assets first, then by symbol — stable catalog ordering
            .order_by(Asset.user_id.is_(None).desc(), Asset.symbol.asc())
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return items, total


def get_asset(db: Session, user_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, *_visible(user_id)))
    if asset is None:
        raise not_found("Asset not found")
    return asset


def get_own_asset(db: Session, user_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    """Only the user's own assets — system assets are read-only for users."""
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.user_id == user_id,
            Asset.deleted_at.is_(None),
        )
    )
    if asset is None:
        raise not_found("Asset not found")
    return asset


def create_asset(db: Session, user_id: uuid.UUID, data: AssetCreate) -> Asset:
    asset = Asset(
        user_id=user_id,
        symbol=data.symbol,
        name=data.name,
        asset_class=data.asset_class,
        unit=data.unit,
        quote_currency=data.quote_currency,
        is_active=True,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(
    db: Session, user_id: uuid.UUID, asset_id: uuid.UUID, data: AssetUpdate
) -> Asset:
    asset = get_own_asset(db, user_id, asset_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)
    db.commit()
    db.refresh(asset)
    return asset
