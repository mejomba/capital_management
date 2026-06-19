import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, page_params
from app.models.asset import AssetClass
from app.schemas.asset import AssetCreate, AssetOut, AssetUpdate
from app.schemas.common import Page
from app.services import asset_service

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=Page[AssetOut])
def list_assets(
    current_user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    asset_class: Annotated[AssetClass | None, Query(alias="class")] = None,
    q: str | None = None,
) -> Page[AssetOut]:
    items, total = asset_service.list_assets(
        db, current_user.id, params, asset_class=asset_class, q=q
    )
    return Page[AssetOut](
        items=[AssetOut.model_validate(a) for a in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    data: AssetCreate, current_user: CurrentUser, db: DbSession
) -> AssetOut:
    asset = asset_service.create_asset(db, current_user.id, data)
    return AssetOut.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(
    asset_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> AssetOut:
    asset = asset_service.get_asset(db, current_user.id, asset_id)
    return AssetOut.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: uuid.UUID,
    data: AssetUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> AssetOut:
    asset = asset_service.update_asset(db, current_user.id, asset_id, data)
    return AssetOut.model_validate(asset)
