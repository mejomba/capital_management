"""Liabilities and their *derived* outstanding balance.

Interest is never double-counted: it enters only through `interest` events, and
a `repayment` settles existing balances through its components — the repayment
`amount` itself is never subtracted from principal (see LiabilityEvent docstring).
"""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import not_found, unprocessable
from app.core.pagination import PageParams
from app.models.audit_log import AuditAction
from app.models.liability import Liability
from app.models.liability_event import LiabilityEvent, LiabilityEventType
from app.schemas.liability import LiabilityCreate, LiabilityEventCreate
from app.services.audit import record_audit


def _get_liability(db: Session, user_id: uuid.UUID, liability_id: uuid.UUID) -> Liability:
    liability = db.scalar(
        select(Liability)
        .options(selectinload(Liability.events))
        .where(
            Liability.id == liability_id,
            Liability.user_id == user_id,
            Liability.deleted_at.is_(None),
        )
    )
    if liability is None:
        raise not_found("Liability not found")
    return liability


def outstanding(liability: Liability, as_of: date | datetime | None = None) -> dict:
    """Derived balance from events (optionally only those at/before `as_of`)."""
    cutoff: datetime | None = None
    if as_of is not None:
        cutoff = (
            as_of
            if isinstance(as_of, datetime)
            else datetime.combine(as_of, time.max, tzinfo=timezone.utc)
        )

    principal_out = Decimal(0)
    interest_unpaid = Decimal(0)
    for ev in liability.events:
        if cutoff is not None and ev.occurred_at > cutoff:
            continue
        if ev.type is LiabilityEventType.disbursement:
            principal_out += ev.amount
        elif ev.type is LiabilityEventType.interest:
            interest_unpaid += ev.amount
        elif ev.type is LiabilityEventType.repayment:
            principal_out -= ev.principal_component or Decimal(0)
            interest_unpaid -= ev.interest_component or Decimal(0)

    total = principal_out + interest_unpaid
    return {
        "currency": liability.currency,
        "principal_outstanding": principal_out,
        "interest_unpaid": interest_unpaid,
        "total_outstanding": total,
    }


def list_liabilities(
    db: Session, user_id: uuid.UUID, params: PageParams
) -> tuple[list[Liability], int]:
    conds = [Liability.user_id == user_id, Liability.deleted_at.is_(None)]
    total = db.scalar(select(func.count()).select_from(Liability).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Liability)
            .options(selectinload(Liability.events))
            .where(*conds)
            .order_by(Liability.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return items, total


def get_liability(db: Session, user_id: uuid.UUID, liability_id: uuid.UUID) -> Liability:
    return _get_liability(db, user_id, liability_id)


def create_liability(db: Session, user_id: uuid.UUID, data: LiabilityCreate) -> Liability:
    liability = Liability(
        user_id=user_id,
        name=data.name,
        type=data.type,
        principal=data.principal,
        currency=data.currency,
        interest_rate=data.interest_rate,
        start_date=data.start_date,
        term_months=data.term_months,
        schedule_json=data.schedule,
    )
    db.add(liability)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type="liability",
        entity_id=liability.id,
        action=AuditAction.create,
        diff={"name": liability.name, "principal": str(liability.principal)},
    )
    db.commit()
    db.refresh(liability)
    return liability


def add_event(
    db: Session,
    user_id: uuid.UUID,
    liability_id: uuid.UUID,
    data: LiabilityEventCreate,
) -> LiabilityEvent:
    liability = _get_liability(db, user_id, liability_id)

    if data.currency != liability.currency:
        raise unprocessable(
            "Event currency must match the liability currency",
            details={"liability_currency": liability.currency, "event_currency": data.currency},
        )

    principal_component = data.principal_component
    interest_component = data.interest_component
    if data.type is LiabilityEventType.repayment:
        if principal_component is None and interest_component is None:
            # default: a pure principal repayment
            principal_component = data.amount
            interest_component = Decimal(0)
        else:
            principal_component = principal_component or Decimal(0)
            interest_component = interest_component or Decimal(0)
            if principal_component + interest_component != data.amount:
                raise unprocessable(
                    "principal_component + interest_component must equal amount",
                    details={
                        "amount": str(data.amount),
                        "principal_component": str(principal_component),
                        "interest_component": str(interest_component),
                    },
                )
    else:
        # disbursement / interest carry no components
        principal_component = None
        interest_component = None

    event = LiabilityEvent(
        liability_id=liability.id,
        type=data.type,
        amount=data.amount,
        currency=data.currency,
        occurred_at=data.occurred_at,
        principal_component=principal_component,
        interest_component=interest_component,
    )
    db.add(event)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type="liability_event",
        entity_id=event.id,
        action=AuditAction.create,
        diff={"liability_id": str(liability.id), "type": event.type.value, "amount": str(event.amount)},
    )
    db.commit()
    db.refresh(event)
    return event


def outstanding_for_all(
    db: Session, user_id: uuid.UUID, as_of: date | datetime | None = None
) -> list[tuple[Liability, dict]]:
    liabilities = db.scalars(
        select(Liability)
        .options(selectinload(Liability.events))
        .where(Liability.user_id == user_id, Liability.deleted_at.is_(None))
    )
    return [(lia, outstanding(lia, as_of)) for lia in liabilities]
