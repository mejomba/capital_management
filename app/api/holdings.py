from datetime import datetime

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.holding import HoldingByAssetOut, HoldingByClassOut, HoldingOut
from app.services import holdings as holdings_service

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingOut])
def list_holdings(
    current_user: CurrentUser,
    db: DbSession,
    as_of: datetime | None = None,
) -> list[HoldingOut]:
    rows = holdings_service.holdings(db, current_user.id, as_of)
    return [HoldingOut.model_validate(r) for r in rows]


@router.get("/by-asset", response_model=list[HoldingByAssetOut])
def holdings_by_asset(
    current_user: CurrentUser,
    db: DbSession,
    as_of: datetime | None = None,
) -> list[HoldingByAssetOut]:
    rows = holdings_service.holdings_by_asset(db, current_user.id, as_of)
    return [HoldingByAssetOut.model_validate(r) for r in rows]


@router.get("/by-class", response_model=list[HoldingByClassOut])
def holdings_by_class(
    current_user: CurrentUser,
    db: DbSession,
    as_of: datetime | None = None,
) -> list[HoldingByClassOut]:
    rows = holdings_service.holdings_by_class(db, current_user.id, as_of)
    return [HoldingByClassOut.model_validate(r) for r in rows]
