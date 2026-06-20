import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.allocation import AllocationOut
from app.schemas.performance import InflationComparisonOut, PerformanceOut
from app.schemas.pnl import PnlOut
from app.schemas.projection import ProjectionOut
from app.schemas.snapshot import NetWorthPoint, NetWorthSeriesOut
from app.services import allocation as allocation_service
from app.services import inflation as inflation_service
from app.services import performance as performance_service
from app.services import pnl as pnl_service
from app.services import projection as projection_service
from app.services import snapshots as snapshot_service

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


@router.get("/net-worth", response_model=NetWorthSeriesOut)
def net_worth_report(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    currency: str = "both",
) -> NetWorthSeriesOut:
    rows = snapshot_service.list_snapshots(db, current_user.id, date_from, date_to)
    return NetWorthSeriesOut(
        currency=currency,
        series=[NetWorthPoint.model_validate(r) for r in rows],
    )


@router.get("/performance", response_model=PerformanceOut)
def performance_report(
    current_user: CurrentUser,
    db: DbSession,
    from_dt: Annotated[datetime, Query(alias="from")],
    to_dt: Annotated[datetime, Query(alias="to")],
) -> PerformanceOut:
    report = performance_service.performance_report(db, current_user.id, from_dt, to_dt)
    return PerformanceOut.model_validate(report)


@router.get("/allocation", response_model=AllocationOut)
def allocation_report(
    current_user: CurrentUser,
    db: DbSession,
    as_of: datetime | None = None,
    currency: str = "IRR",
    goal_id: uuid.UUID | None = None,
) -> AllocationOut:
    report = allocation_service.allocation_report(
        db, current_user.id, as_of, currency, goal_id
    )
    return AllocationOut.model_validate(report)


@router.get("/inflation-comparison", response_model=InflationComparisonOut)
def inflation_comparison(
    current_user: CurrentUser,
    db: DbSession,
    from_dt: Annotated[datetime, Query(alias="from")],
    to_dt: Annotated[datetime, Query(alias="to")],
) -> InflationComparisonOut:
    report = inflation_service.inflation_comparison(db, current_user.id, from_dt, to_dt)
    return InflationComparisonOut.model_validate(report)


@router.get("/projection", response_model=ProjectionOut)
def projection_report(
    current_user: CurrentUser,
    db: DbSession,
    horizon_months: int = 12,
    monthly_contribution: Decimal = Decimal(0),
    scenario: Literal["pessimistic", "realistic", "optimistic"] | None = None,
) -> ProjectionOut:
    report = projection_service.project(
        db, current_user.id, horizon_months, monthly_contribution, scenario
    )
    return ProjectionOut.model_validate(report)
