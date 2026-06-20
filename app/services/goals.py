"""Goals and their *derived* progress (never stored)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.core.pagination import PageParams
from app.models.audit_log import AuditAction
from app.models.goal import Goal, GoalStatus, GoalType
from app.schemas.goal import GoalCreate, GoalUpdate
from app.services import holdings as holdings_service
from app.services import net_worth
from app.services import valuation
from app.services.audit import record_audit

_DEFAULT_CURRENCY = valuation.IRR


def _get_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    goal = db.scalar(
        select(Goal).where(
            Goal.id == goal_id,
            Goal.user_id == user_id,
            Goal.deleted_at.is_(None),
        )
    )
    if goal is None:
        raise not_found("Goal not found")
    return goal


def list_goals(db: Session, user_id: uuid.UUID, params: PageParams) -> tuple[list[Goal], int]:
    conds = [Goal.user_id == user_id, Goal.deleted_at.is_(None)]
    total = db.scalar(select(func.count()).select_from(Goal).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Goal)
            .where(*conds)
            .order_by(Goal.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return items, total


def get_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    return _get_goal(db, user_id, goal_id)


def create_goal(db: Session, user_id: uuid.UUID, data: GoalCreate) -> Goal:
    goal = Goal(
        user_id=user_id,
        type=data.type,
        title=data.title,
        target_value=data.target_value,
        currency=data.currency,
        target_allocation_json=data.target_allocation,
        target_date=data.target_date,
        status=data.status or GoalStatus.active,
    )
    db.add(goal)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type="goal",
        entity_id=goal.id,
        action=AuditAction.create,
        diff={"type": goal.type.value, "title": goal.title},
    )
    db.commit()
    db.refresh(goal)
    return goal


def update_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, data: GoalUpdate) -> Goal:
    goal = _get_goal(db, user_id, goal_id)
    changes = data.model_dump(exclude_unset=True)
    field_map = {"target_allocation": "target_allocation_json"}
    for key, value in changes.items():
        setattr(goal, field_map.get(key, key), value)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type="goal",
        entity_id=goal.id,
        action=AuditAction.update,
        diff={k: (v.value if hasattr(v, "value") else str(v)) for k, v in changes.items()},
    )
    db.commit()
    db.refresh(goal)
    return goal


# --- progress --------------------------------------------------------------

def compute_progress(db: Session, user_id: uuid.UUID, goal: Goal) -> dict:
    if goal.type is GoalType.target_net_worth:
        return _progress_net_worth(db, user_id, goal)
    if goal.type is GoalType.target_allocation:
        return _progress_allocation(db, user_id, goal)
    if goal.type is GoalType.target_return:
        return {
            "type": goal.type.value,
            "pending": True,
            "percent": None,
            "reason": "Requires return metrics (XIRR/TWR), available in M5",
        }
    # custom: simple manual completion based on status
    return {
        "type": goal.type.value,
        "percent": "100" if goal.status is GoalStatus.achieved else None,
    }


def _s(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _progress_net_worth(db: Session, user_id: uuid.UUID, goal: Goal) -> dict:
    currency = (goal.currency or _DEFAULT_CURRENCY).upper()
    nw = net_worth.compute_live(db, user_id, datetime.now(timezone.utc))
    current = nw["net_worth_usd"] if currency == valuation.USD else nw["net_worth_irr"]

    percent = None
    remaining = None
    if goal.target_value is not None and goal.target_value != 0:
        percent = current / goal.target_value * Decimal(100)
        remaining = goal.target_value - current
    return {
        "type": goal.type.value,
        "currency": currency,
        "current_value": _s(current),
        "target_value": _s(goal.target_value),
        "remaining": _s(remaining),
        "percent": _s(percent),
        "achieved": percent is not None and percent >= Decimal(100),
    }


def _progress_allocation(db: Session, user_id: uuid.UUID, goal: Goal) -> dict:
    currency = (goal.currency or _DEFAULT_CURRENCY).upper()
    field = "value_usd" if currency == valuation.USD else "value_irr"

    by_class = holdings_service.valued_by_class(db, user_id, datetime.now(timezone.utc))
    class_values: dict[str, Decimal] = {}
    for cls in by_class:
        total = sum(
            (i[field] for i in cls["items"] if i[field] is not None), Decimal(0)
        )
        class_values[cls["asset_class"].value] = total
    grand_total = sum(class_values.values(), Decimal(0))

    target = {k: Decimal(str(v)) for k, v in (goal.target_allocation_json or {}).items()}
    current_alloc: dict[str, Decimal] = {}
    if grand_total != 0:
        current_alloc = {k: v / grand_total for k, v in class_values.items()}

    # drift over the union of classes; percent = 1 - total-variation distance
    keys = set(target) | set(current_alloc)
    drift = {k: current_alloc.get(k, Decimal(0)) - target.get(k, Decimal(0)) for k in keys}
    tvd = sum((abs(d) for d in drift.values()), Decimal(0)) / Decimal(2)
    percent = (Decimal(1) - tvd) * Decimal(100)

    return {
        "type": goal.type.value,
        "currency": currency,
        "current_allocation": {k: str(v) for k, v in current_alloc.items()},
        "target_allocation": {k: str(v) for k, v in target.items()},
        "drift": {k: str(v) for k, v in drift.items()},
        "percent": _s(percent),
        "achieved": goal.status is GoalStatus.achieved,
    }
