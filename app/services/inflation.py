"""Inflation series, cumulative inflation, and hurdle-rate resolution."""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assumptions import HurdleMode
from app.models.inflation_rate import InflationRate
from app.services import assumptions as assumptions_service
from app.services import valuation


def _months_in_range(from_d: date, to_d: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    year, month = from_d.year, from_d.month
    while (year, month) <= (to_d.year, to_d.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def cumulative_inflation(
    db: Session, user_id: uuid.UUID, from_d: date, to_d: date
) -> Decimal:
    """Compound the monthly rates whose period falls in [from, to]. Missing
    months count as 0% (no inflation recorded)."""
    if to_d < from_d:
        return Decimal(0)
    rows = db.scalars(
        select(InflationRate).where(InflationRate.user_id == user_id)
    )
    by_period = {(r.period_year, r.period_month): r.rate for r in rows}

    factor = Decimal(1)
    for year, month in _months_in_range(from_d, to_d):
        rate = by_period.get((year, month), Decimal(0))
        factor *= Decimal(1) + rate
    return factor - Decimal(1)


def resolve_hurdle(
    db: Session, user_id: uuid.UUID, from_d: date, to_d: date
) -> dict:
    """The success threshold over the window, per assumptions.hurdle_mode."""
    settings = assumptions_service.get_assumptions(db, user_id)
    mode = settings.hurdle_mode

    if mode is HurdleMode.fixed:
        rate = settings.hurdle_fixed_rate or Decimal(0)
    elif mode is HurdleMode.inflation:
        rate = cumulative_inflation(db, user_id, from_d, to_d)
    else:  # usd_growth: rial devaluation vs USD over the window
        rate = _usd_growth(db, user_id, from_d, to_d)

    return {"mode": mode.value, "rate": rate}


def _usd_growth(
    db: Session, user_id: uuid.UUID, from_d: date, to_d: date
) -> Decimal:
    fx_from = valuation.fx_usd_irr(db, user_id, from_d)
    fx_to = valuation.fx_usd_irr(db, user_id, to_d)
    if not fx_from or not fx_to or fx_from == 0:
        return Decimal(0)
    return fx_to / fx_from - Decimal(1)


def inflation_comparison(
    db: Session, user_id: uuid.UUID, from_dt: datetime, to_dt: datetime
) -> dict:
    from app.services import performance as perf  # local import avoids cycle

    report = perf.performance_report(db, user_id, from_dt, to_dt)
    inflation_cum = Decimal(report["inflation_cumulative"])
    hurdle = resolve_hurdle(db, user_id, from_dt.date(), to_dt.date())

    nominal_irr = report["irr"]["nominal"]
    nominal_dec = Decimal(nominal_irr) if nominal_irr is not None else None

    return {
        "from_dt": from_dt,
        "to_dt": to_dt,
        "nominal_irr": report["irr"]["nominal"],
        "real_irr": report["irr"]["real"],
        "usd_based": report["usd_based"],
        "inflation": str(inflation_cum),
        "hurdle": {"mode": hurdle["mode"], "rate": str(hurdle["rate"])},
        "beats_inflation": (
            None if nominal_dec is None else nominal_dec > inflation_cum
        ),
        "beats_hurdle": (
            None if nominal_dec is None else nominal_dec > hurdle["rate"]
        ),
    }
