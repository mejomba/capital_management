"""Current vs target asset-class allocation, drift, and rebalance suggestions."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus, GoalType
from app.services import holdings as holdings_service
from app.services import valuation


def _target_from_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID | None) -> dict:
    conds = [
        Goal.user_id == user_id,
        Goal.deleted_at.is_(None),
        Goal.type == GoalType.target_allocation,
    ]
    if goal_id is not None:
        conds.append(Goal.id == goal_id)
    else:
        conds.append(Goal.status == GoalStatus.active)
    goal = db.scalar(select(Goal).where(*conds).order_by(Goal.created_at.desc()))
    if goal is None or not goal.target_allocation_json:
        return {}
    return {k: Decimal(str(v)) for k, v in goal.target_allocation_json.items()}


def allocation_report(
    db: Session,
    user_id: uuid.UUID,
    as_of: datetime | None = None,
    currency: str = valuation.IRR,
    goal_id: uuid.UUID | None = None,
) -> dict:
    eff = as_of or datetime.now(timezone.utc)
    currency = currency.upper()
    field = "value_usd" if currency == valuation.USD else "value_irr"

    class_values: dict[str, Decimal] = {}
    for cls in holdings_service.valued_by_class(db, user_id, eff):
        total = sum((i[field] for i in cls["items"] if i[field] is not None), Decimal(0))
        class_values[cls["asset_class"].value] = total
    grand_total = sum(class_values.values(), Decimal(0))

    current = (
        {k: v / grand_total for k, v in class_values.items()}
        if grand_total != 0
        else {}
    )
    target = _target_from_goal(db, user_id, goal_id)

    keys = sorted(set(current) | set(target) | set(class_values))
    drift = {k: current.get(k, Decimal(0)) - target.get(k, Decimal(0)) for k in keys}

    rebalance = []
    for k in keys:
        target_value = target.get(k, Decimal(0)) * grand_total
        current_value = class_values.get(k, Decimal(0))
        delta = target_value - current_value
        rebalance.append(
            {
                "asset_class": k,
                "current_value": str(current_value),
                "target_value": str(target_value),
                "action": "buy" if delta > 0 else ("sell" if delta < 0 else "hold"),
                "amount": str(abs(delta)),
                "delta": str(delta),
            }
        )

    return {
        "as_of": eff,
        "currency": currency,
        "total_value": str(grand_total),
        "current": {k: str(v) for k, v in current.items()},
        "target": {k: str(v) for k, v in target.items()},
        "drift": {k: str(v) for k, v in drift.items()},
        "rebalance": rebalance,
    }
