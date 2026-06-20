"""Forward projection of net worth under three growth scenarios."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services import assumptions as assumptions_service
from app.services import holdings as holdings_service
from app.services import net_worth as net_worth_service
from app.services import valuation

# Scenario = multiplier applied to the assumed annual growth rate.
SCENARIOS = {
    "pessimistic": Decimal("0.5"),
    "realistic": Decimal("1.0"),
    "optimistic": Decimal("1.5"),
}


def _monthly_rate(annual: Decimal, factor: Decimal) -> Decimal:
    base = 1.0 + float(annual) * float(factor)
    if base <= 0:
        return Decimal(-1)
    return Decimal(repr(base ** (1.0 / 12.0) - 1.0))


def project(
    db: Session,
    user_id: uuid.UUID,
    horizon_months: int,
    monthly_contribution: Decimal,
    scenario: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    settings = assumptions_service.get_assumptions(db, user_id)
    growth = {k: Decimal(str(v)) for k, v in (settings.growth_assumptions_json or {}).items()}

    class_values: dict[str, Decimal] = {}
    for cls in holdings_service.valued_by_class(db, user_id, now):
        total = sum((i["value_irr"] for i in cls["items"] if i["value_irr"] is not None), Decimal(0))
        class_values[cls["asset_class"].value] = total
    grand_total = sum(class_values.values(), Decimal(0))
    weights = (
        {k: v / grand_total for k, v in class_values.items()}
        if grand_total != 0
        else {}
    )

    nw = net_worth_service.compute_live(db, user_id, now)
    liabilities_irr = nw["total_liabilities_irr"]
    fx = valuation.fx_usd_irr(db, user_id, now)

    names = [scenario] if scenario in SCENARIOS else list(SCENARIOS)
    scenarios_out: dict[str, list] = {}
    for name in names:
        factor = SCENARIOS[name]
        values = dict(class_values)
        # ensure a bucket for contributions when the portfolio is empty
        if not weights:
            values.setdefault("fiat", Decimal(0))
        series = []
        for month in range(1, horizon_months + 1):
            for cls in list(values):
                rate = _monthly_rate(growth.get(cls, Decimal(0)), factor)
                values[cls] *= Decimal(1) + rate
            if weights:
                for cls, w in weights.items():
                    values[cls] += monthly_contribution * w
            else:
                values["fiat"] += monthly_contribution

            assets_irr = sum(values.values(), Decimal(0))
            net_irr = assets_irr - liabilities_irr
            net_usd = (net_irr / fx) if fx else None
            series.append(
                {
                    "month": month,
                    "net_worth_irr": str(net_irr),
                    "net_worth_usd": str(net_usd) if net_usd is not None else None,
                }
            )
        scenarios_out[name] = series

    return {
        "horizon_months": horizon_months,
        "monthly_contribution": str(monthly_contribution),
        "scenarios": scenarios_out,
    }
