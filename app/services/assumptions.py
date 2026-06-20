"""Per-user assumptions (get-or-default + upsert) and the inflation series."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assumptions import Assumptions, DisplayCurrency, HurdleMode
from app.models.inflation_rate import InflationRate
from app.schemas.assumptions import AssumptionsUpdate
from app.schemas.inflation import InflationRateCreate


def get_assumptions(db: Session, user_id: uuid.UUID) -> Assumptions:
    """Return the user's assumptions, or a transient default (not persisted)."""
    existing = db.scalar(select(Assumptions).where(Assumptions.user_id == user_id))
    if existing is not None:
        return existing
    return Assumptions(
        user_id=user_id,
        display_currency=DisplayCurrency.both,
        hurdle_mode=HurdleMode.inflation,
        hurdle_fixed_rate=None,
        growth_assumptions_json={},
    )


def upsert_assumptions(
    db: Session, user_id: uuid.UUID, data: AssumptionsUpdate
) -> Assumptions:
    settings = db.scalar(select(Assumptions).where(Assumptions.user_id == user_id))
    if settings is None:
        settings = Assumptions(user_id=user_id)
        db.add(settings)
    settings.display_currency = data.display_currency
    settings.hurdle_mode = data.hurdle_mode
    settings.hurdle_fixed_rate = data.hurdle_fixed_rate
    settings.growth_assumptions_json = data.growth_assumptions or {}
    db.commit()
    db.refresh(settings)
    return settings


def list_inflation(db: Session, user_id: uuid.UUID) -> list[InflationRate]:
    return list(
        db.scalars(
            select(InflationRate)
            .where(InflationRate.user_id == user_id)
            .order_by(InflationRate.period_year, InflationRate.period_month)
        )
    )


def upsert_inflation(
    db: Session, user_id: uuid.UUID, data: InflationRateCreate
) -> InflationRate:
    row = db.scalar(
        select(InflationRate).where(
            InflationRate.user_id == user_id,
            InflationRate.period_year == data.period_year,
            InflationRate.period_month == data.period_month,
        )
    )
    if row is None:
        row = InflationRate(
            user_id=user_id,
            period_year=data.period_year,
            period_month=data.period_month,
        )
        db.add(row)
    row.rate = data.rate
    row.source = data.source
    db.commit()
    db.refresh(row)
    return row
