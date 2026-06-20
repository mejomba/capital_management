"""Portfolio performance: money-weighted (XIRR) and time-weighted (TWR) return,
computed natively in each currency (IRR and USD) with date-accurate FX.

Cash-flow rule (the classic correctness trap): only `deposit` and `withdrawal`
are external flows. `income` (dividends/rent/staking), `trade`, and `transfer`
are NOT contributions — income is part of the return and is captured by the
growth in ending value. Counting income as a contribution would double-count it
and understate the true return.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services import holdings as holdings_service
from app.services import inflation as inflation_service
from app.services import valuation

# Allow-list: the ONLY transaction types that are external cash flows.
_EXTERNAL_FLOW_TYPES = {TransactionType.deposit, TransactionType.withdrawal}


def assets_value(
    db: Session, user_id: uuid.UUID, as_of: datetime, currency: str
) -> Decimal:
    """Total market value of held assets (not net worth) in `currency`."""
    field = "value_usd" if currency == valuation.USD else "value_irr"
    rows = holdings_service.valued_holdings(db, user_id, as_of)
    return sum((r[field] for r in rows if r[field] is not None), Decimal(0))


def external_cashflows(
    db: Session,
    user_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
    currency: str,
) -> list[tuple[datetime, Decimal]]:
    """External flows in (from, to], valued natively in `currency` at each flow's
    own date. Investor sign: deposit negative, withdrawal positive."""
    txns = db.scalars(
        select(Transaction)
        .options(selectinload(Transaction.legs))
        .where(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.active,
            Transaction.deleted_at.is_(None),
            Transaction.type.in_(_EXTERNAL_FLOW_TYPES),
            Transaction.occurred_at > from_dt,
            Transaction.occurred_at <= to_dt,
        )
        .order_by(Transaction.occurred_at)
    )

    by_time: dict[datetime, Decimal] = {}
    asset_cache: dict[uuid.UUID, Asset] = {}
    for txn in txns:
        flow = Decimal(0)
        for leg in txn.legs:
            asset = asset_cache.get(leg.asset_id) or db.get(Asset, leg.asset_id)
            asset_cache[asset.id] = asset
            unit = valuation.market_unit_value(
                db, user_id, asset, currency, txn.occurred_at
            )
            if unit is None:
                continue
            # investor sign: money INTO the portfolio (deposit, qty>0) is negative
            flow += -(leg.quantity * unit)
        by_time[txn.occurred_at] = by_time.get(txn.occurred_at, Decimal(0)) + flow
    return sorted(by_time.items())


# --- XIRR ------------------------------------------------------------------

def _npv(rate: float, amounts: list[float], years: list[float]) -> float:
    return sum(a / (1.0 + rate) ** y for a, y in zip(amounts, years))


def xirr(cashflows: list[tuple[datetime, Decimal]]) -> Decimal | None:
    """Annualised money-weighted return. None if it cannot be solved."""
    flows = [(d, float(a)) for d, a in cashflows if a != 0]
    if len(flows) < 2:
        return None
    amounts = [a for _, a in flows]
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        return None

    t0 = min(d for d, _ in flows)
    years = [(d - t0).days / 365.0 for d, _ in flows]

    # Newton's method, then bisection fallback.
    rate = 0.1
    for _ in range(100):
        try:
            value = _npv(rate, amounts, years)
            deriv = sum(
                -y * a / (1.0 + rate) ** (y + 1.0) for a, y in zip(amounts, years)
            )
        except (OverflowError, ZeroDivisionError, ValueError):
            break
        if deriv == 0:
            break
        new_rate = rate - value / deriv
        if new_rate <= -0.9999:
            break
        if abs(new_rate - rate) < 1e-10:
            rate = new_rate
            if abs(_npv(rate, amounts, years)) < 1e-6:
                return Decimal(repr(rate))
            break
        rate = new_rate
        if abs(value) < 1e-9:
            return Decimal(repr(rate))

    return _bisection(amounts, years)


def _bisection(amounts: list[float], years: list[float]) -> Decimal | None:
    low, high = -0.9999, 10.0
    f_low = _npv(low, amounts, years)
    step = 0.01
    r = low + step
    prev_r, prev_f = low, f_low
    while r <= high:
        f = _npv(r, amounts, years)
        if prev_f == 0:
            return Decimal(repr(prev_r))
        if (prev_f < 0) != (f < 0):
            lo, hi = prev_r, r
            for _ in range(200):
                mid = (lo + hi) / 2
                fm = _npv(mid, amounts, years)
                if abs(fm) < 1e-9:
                    return Decimal(repr(mid))
                if (fm < 0) == (_npv(lo, amounts, years) < 0):
                    lo = mid
                else:
                    hi = mid
            return Decimal(repr((lo + hi) / 2))
        prev_r, prev_f = r, f
        r += step
    return None


# --- TWR -------------------------------------------------------------------

def twr(
    db: Session,
    user_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
    currency: str,
) -> Decimal | None:
    """Cumulative time-weighted return: chain sub-period returns, breaking the
    window at each external flow."""
    # portfolio-side amounts (deposit positive) = negation of investor cashflows
    flows = [(t, -cf) for t, cf in external_cashflows(db, user_id, from_dt, to_dt, currency)]

    prev_value = assets_value(db, user_id, from_dt, currency)
    chain = Decimal(1)
    for t, amount in flows:
        v_before = assets_value(db, user_id, t - timedelta(microseconds=1), currency)
        if prev_value != 0:
            chain *= v_before / prev_value
        prev_value = v_before + amount

    v_end = assets_value(db, user_id, to_dt, currency)
    if prev_value != 0:
        chain *= v_end / prev_value
    return chain - Decimal(1)


# --- report ----------------------------------------------------------------

def _build_flows(
    db: Session, user_id: uuid.UUID, from_dt: datetime, to_dt: datetime, ccy: str
) -> list[tuple[datetime, Decimal]]:
    v_start = assets_value(db, user_id, from_dt, ccy)
    v_end = assets_value(db, user_id, to_dt, ccy)
    flows: list[tuple[datetime, Decimal]] = [(from_dt, -v_start)]
    flows += external_cashflows(db, user_id, from_dt, to_dt, ccy)
    flows.append((to_dt, v_end))
    return flows


def _currency_block(
    db: Session,
    user_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
    ccy: str,
    inflation_cum: Decimal,
) -> dict:
    x = xirr(_build_flows(db, user_id, from_dt, to_dt, ccy))
    t = twr(db, user_id, from_dt, to_dt, ccy)
    nominal = t
    real = None
    if nominal is not None:
        real = (Decimal(1) + nominal) / (Decimal(1) + inflation_cum) - Decimal(1)
    return {
        "xirr": _s(x),
        "twr": _s(t),
        "nominal": _s(nominal),
        "real": _s(real),
    }


def _s(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def performance_report(
    db: Session, user_id: uuid.UUID, from_dt: datetime, to_dt: datetime
) -> dict:
    inflation_cum = inflation_service.cumulative_inflation(
        db, user_id, from_dt.date(), to_dt.date()
    )
    irr_block = _currency_block(db, user_id, from_dt, to_dt, valuation.IRR, inflation_cum)
    usd_block = _currency_block(db, user_id, from_dt, to_dt, valuation.USD, inflation_cum)
    return {
        "from_dt": from_dt,
        "to_dt": to_dt,
        "irr": irr_block,
        "usd": usd_block,
        "inflation_cumulative": str(inflation_cum),
        "usd_based": usd_block["nominal"],
    }
