from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.pnl import PnlOut
from app.services import pnl as pnl_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/pnl", response_model=PnlOut)
def pnl_report(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    group_by: Literal["class", "account", "asset"] | None = None,
) -> PnlOut:
    report = pnl_service.pnl_report(
        db, current_user.id, date_from, date_to, group_by
    )
    return PnlOut.model_validate(report)
