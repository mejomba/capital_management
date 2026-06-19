"""Transaction ledger: create / get / list / reverse / soft-delete with
per-type validation, the non-negative-balance invariant, and audit logging."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import not_found, unprocessable
from app.core.pagination import PageParams
from app.models.account import Account
from app.models.asset import Asset
from app.models.audit_log import AuditAction
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.transaction_leg import TransactionLeg
from app.services import holdings as holdings_service
from app.services import lots as lots_service
from app.services.audit import record_audit

SINGLE_LEG_TYPES = {
    TransactionType.deposit,
    TransactionType.withdrawal,
    TransactionType.income,
    TransactionType.fee,
    TransactionType.expense,
}
# inbound (+) vs outbound (-) sign for the single-leg flat types
_INBOUND = {TransactionType.deposit, TransactionType.income}


@dataclass
class LegSpec:
    account_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal
    unit_price: Decimal | None = None
    price_currency: str | None = None
    fee: Decimal | None = None
    fee_currency: str | None = None


@dataclass
class TxnFilters:
    type: TransactionType | None = None
    account_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --- validation ------------------------------------------------------------

def _load_scoped_entities(
    db: Session, user_id: uuid.UUID, specs: list[LegSpec]
) -> dict[uuid.UUID, Asset]:
    """Verify every referenced account belongs to the user and every asset is
    visible (own or system). Returns asset_id -> Asset map. Raises 422 on miss,
    without revealing whether the id exists for another user."""
    account_ids = {s.account_id for s in specs}
    asset_ids = {s.asset_id for s in specs}

    owned_accounts = set(
        db.scalars(
            select(Account.id).where(
                Account.id.in_(account_ids),
                Account.user_id == user_id,
                Account.deleted_at.is_(None),
            )
        )
    )
    missing_accounts = account_ids - owned_accounts
    if missing_accounts:
        raise unprocessable(
            "Unknown or inaccessible account",
            details={"account_ids": [str(a) for a in missing_accounts]},
        )

    assets = {
        a.id: a
        for a in db.scalars(
            select(Asset).where(
                Asset.id.in_(asset_ids),
                ((Asset.user_id == user_id) | (Asset.user_id.is_(None))),
                Asset.deleted_at.is_(None),
            )
        )
    }
    missing_assets = asset_ids - set(assets)
    if missing_assets:
        raise unprocessable(
            "Unknown or inaccessible asset",
            details={"asset_ids": [str(a) for a in missing_assets]},
        )
    return assets


def _build_specs(data) -> list[LegSpec]:
    """Normalise the typed request body into signed LegSpecs and apply the
    per-type structural rules (GLOSSARY.md)."""
    ttype: TransactionType = data.type

    if ttype in SINGLE_LEG_TYPES:
        sign = Decimal(1) if ttype in _INBOUND else Decimal(-1)
        return [
            LegSpec(
                account_id=data.account_id,
                asset_id=data.asset_id,
                quantity=sign * data.quantity,
                unit_price=data.unit_price,
                price_currency=data.price_currency,
                fee=data.fee,
                fee_currency=data.fee_currency,
            )
        ]

    # multi-leg: trade / transfer (schema already guarantees exactly 2 legs)
    legs = data.legs
    for leg in legs:
        if leg.quantity == 0:
            raise unprocessable("Leg quantity must not be zero")

    negatives = [leg for leg in legs if leg.quantity < 0]
    positives = [leg for leg in legs if leg.quantity > 0]
    if len(negatives) != 1 or len(positives) != 1:
        raise unprocessable(
            f"A {ttype.value} must have exactly one outflow (-) and one inflow (+) leg"
        )
    out_leg, in_leg = negatives[0], positives[0]

    if ttype is TransactionType.trade:
        if out_leg.asset_id == in_leg.asset_id:
            raise unprocessable("A trade must reference two different assets")
    else:  # transfer
        if out_leg.asset_id != in_leg.asset_id:
            raise unprocessable("A transfer must move the same asset")
        if out_leg.account_id == in_leg.account_id:
            raise unprocessable("A transfer must use two different accounts")
        fee = data.fee or Decimal(0)
        if out_leg.quantity + in_leg.quantity + fee != 0:
            raise unprocessable(
                "Transfer legs are not consistent: outflow must equal inflow plus fee",
                details={
                    "outflow": str(-out_leg.quantity),
                    "inflow": str(in_leg.quantity),
                    "fee": str(fee),
                },
            )

    specs = [
        LegSpec(
            account_id=leg.account_id,
            asset_id=leg.asset_id,
            quantity=leg.quantity,
            unit_price=leg.unit_price,
            price_currency=leg.price_currency,
        )
        for leg in legs
    ]
    # Attach the transaction-level fee to the outflow leg (record-keeping;
    # fees do not affect M2 holdings — they feed cost-basis in M3).
    if data.fee:
        out_index = next(i for i, leg in enumerate(legs) if leg.quantity < 0)
        specs[out_index].fee = data.fee
        specs[out_index].fee_currency = data.fee_currency
    return specs


def _assert_non_negative(
    db: Session, user_id: uuid.UUID, pairs: set[tuple[uuid.UUID, uuid.UUID]]
) -> None:
    current = holdings_service.holding_for_pairs(db, user_id, pairs)
    offenders = [
        {"account_id": str(a), "asset_id": str(s), "holding": str(q)}
        for (a, s), q in current.items()
        if q < 0
    ]
    if offenders:
        raise unprocessable(
            "Insufficient balance: this would drive a holding negative",
            details={"holdings": offenders},
        )


# --- commands --------------------------------------------------------------

def create_transaction(db: Session, user_id: uuid.UUID, data) -> Transaction:
    specs = _build_specs(data)
    _load_scoped_entities(db, user_id, specs)

    txn = Transaction(
        user_id=user_id,
        type=data.type,
        occurred_at=_to_utc(data.occurred_at),
        note=data.note,
        status=TransactionStatus.active,
    )
    txn.legs = [
        TransactionLeg(
            account_id=s.account_id,
            asset_id=s.asset_id,
            quantity=s.quantity,
            unit_price=s.unit_price,
            price_currency=s.price_currency,
            fee=s.fee,
            fee_currency=s.fee_currency,
        )
        for s in specs
    ]
    db.add(txn)
    db.flush()

    _assert_non_negative(db, user_id, {(s.account_id, s.asset_id) for s in specs})

    lots_service.rebuild_for_assets(db, user_id, {s.asset_id for s in specs})

    record_audit(
        db,
        user_id=user_id,
        entity_type="transaction",
        entity_id=txn.id,
        action=AuditAction.create,
        diff={
            "type": txn.type.value,
            "occurred_at": txn.occurred_at.isoformat(),
            "legs": [
                {
                    "account_id": str(s.account_id),
                    "asset_id": str(s.asset_id),
                    "quantity": str(s.quantity),
                }
                for s in specs
            ],
        },
    )
    db.commit()
    db.refresh(txn)
    return txn


def get_transaction(db: Session, user_id: uuid.UUID, txn_id: uuid.UUID) -> Transaction:
    txn = db.scalar(
        select(Transaction)
        .options(selectinload(Transaction.legs))
        .where(
            Transaction.id == txn_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
    )
    if txn is None:
        raise not_found("Transaction not found")
    return txn


def list_transactions(
    db: Session, user_id: uuid.UUID, filters: TxnFilters, params: PageParams
) -> tuple[list[Transaction], int]:
    conds = [Transaction.user_id == user_id, Transaction.deleted_at.is_(None)]
    if filters.type is not None:
        conds.append(Transaction.type == filters.type)
    if filters.date_from is not None:
        conds.append(Transaction.occurred_at >= _to_utc(filters.date_from))
    if filters.date_to is not None:
        conds.append(Transaction.occurred_at <= _to_utc(filters.date_to))

    leg_filter = []
    if filters.account_id is not None:
        leg_filter.append(TransactionLeg.account_id == filters.account_id)
    if filters.asset_id is not None:
        leg_filter.append(TransactionLeg.asset_id == filters.asset_id)
    if leg_filter:
        conds.append(
            select(TransactionLeg.id)
            .where(TransactionLeg.transaction_id == Transaction.id, *leg_filter)
            .exists()
        )

    total = db.scalar(select(func.count()).select_from(Transaction).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Transaction)
            .options(selectinload(Transaction.legs))
            .where(*conds)
            .order_by(Transaction.occurred_at.desc(), Transaction.id)
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return items, total


def reverse_transaction(
    db: Session, user_id: uuid.UUID, txn_id: uuid.UUID
) -> Transaction:
    original = get_transaction(db, user_id, txn_id)
    if original.status is not TransactionStatus.active:
        raise unprocessable("Only active transactions can be reversed")

    reversal = Transaction(
        user_id=user_id,
        type=original.type,
        occurred_at=datetime.now(timezone.utc),
        note=f"Reversal of {original.id}",
        status=TransactionStatus.reversed,
        reversal_of=original.id,
    )
    reversal.legs = [
        TransactionLeg(
            account_id=leg.account_id,
            asset_id=leg.asset_id,
            quantity=-leg.quantity,
            unit_price=leg.unit_price,
            price_currency=leg.price_currency,
            fee=leg.fee,
            fee_currency=leg.fee_currency,
        )
        for leg in original.legs
    ]
    original.status = TransactionStatus.reversed
    db.add(reversal)
    db.flush()

    # Removing the original from active holdings must not leave anything negative.
    affected_assets = {leg.asset_id for leg in original.legs}
    _assert_non_negative(
        db, user_id, {(leg.account_id, leg.asset_id) for leg in original.legs}
    )

    lots_service.rebuild_for_assets(db, user_id, affected_assets)

    record_audit(
        db,
        user_id=user_id,
        entity_type="transaction",
        entity_id=original.id,
        action=AuditAction.reverse,
        diff={"reversal_of": str(original.id), "reversal_transaction": str(reversal.id)},
    )
    db.commit()
    db.refresh(reversal)
    return reversal


def delete_transaction(db: Session, user_id: uuid.UUID, txn_id: uuid.UUID) -> None:
    txn = get_transaction(db, user_id, txn_id)
    affected_assets = {leg.asset_id for leg in txn.legs}
    pairs = {(leg.account_id, leg.asset_id) for leg in txn.legs}

    txn.deleted_at = datetime.now(timezone.utc)
    db.flush()

    # Soft-deleting an active transaction must not drive any holding negative
    # (mirrors reverse, and keeps lot reconstruction consistent).
    _assert_non_negative(db, user_id, pairs)
    lots_service.rebuild_for_assets(db, user_id, affected_assets)

    record_audit(
        db,
        user_id=user_id,
        entity_type="transaction",
        entity_id=txn.id,
        action=AuditAction.delete,
        diff={"status": txn.status.value},
    )
    db.commit()
