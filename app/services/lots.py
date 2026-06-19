"""FIFO lot engine.

Lots and consumptions are a *materialised projection*: a deterministic function
of the active transactions for a (user, asset), replayed in occurred_at order.
Any change (create / reverse / soft-delete / backdated insert) rebuilds the
affected (user, asset) from scratch — never a delta mutation (CLAUDE.md, M3 #4).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import unprocessable
from app.models.asset import Asset, AssetClass
from app.models.lot import Lot
from app.models.lot_consumption import LotConsumption
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.transaction_leg import TransactionLeg
from app.services import valuation
from app.services.cost_basis import DEFAULT_STRATEGY

_INCREASE_NO_PNL_CONSUME = {
    TransactionType.withdrawal,
    TransactionType.fee,
    TransactionType.expense,
}


@dataclass
class _ConsumptionSpec:
    lot: Lot
    sell_leg_id: uuid.UUID
    qty: Decimal
    proceeds_unit_price: Decimal | None
    proceeds_currency: str | None
    realized_irr: Decimal | None
    realized_usd: Decimal | None
    consumed_at: object


def rebuild(db: Session, user_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return

    _delete_existing(db, user_id, asset_id)

    txns = list(
        db.scalars(
            select(Transaction)
            .options(selectinload(Transaction.legs))
            .where(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.active,
                Transaction.deleted_at.is_(None),
                select(TransactionLeg.id)
                .where(
                    TransactionLeg.transaction_id == Transaction.id,
                    TransactionLeg.asset_id == asset_id,
                )
                .exists(),
            )
            .order_by(
                Transaction.occurred_at, Transaction.created_at, Transaction.id
            )
        )
    )

    open_by_account: dict[uuid.UUID, list[Lot]] = {}
    new_lots: list[Lot] = []
    consumptions: list[_ConsumptionSpec] = []

    for txn in txns:
        legs_here = [leg for leg in txn.legs if leg.asset_id == asset_id]
        if txn.type is TransactionType.transfer:
            _replay_transfer(
                db, user_id, asset, txn, legs_here, open_by_account, new_lots
            )
            continue
        for leg in legs_here:
            if leg.quantity > 0:
                lot = _make_increase_lot(
                    db, user_id, asset, txn, leg, leg.quantity, leg.account_id
                )
                open_by_account.setdefault(leg.account_id, []).append(lot)
                new_lots.append(lot)
            elif leg.quantity < 0:
                realize = txn.type is TransactionType.trade
                segments = _consume(
                    open_by_account.get(leg.account_id, []), -leg.quantity, asset, txn
                )
                if realize:
                    consumptions.extend(
                        _realize(db, user_id, asset, txn, leg, segments)
                    )

    db.add_all(new_lots)
    db.flush()
    for spec in consumptions:
        db.add(
            LotConsumption(
                lot_id=spec.lot.id,
                sell_leg_id=spec.sell_leg_id,
                qty_consumed=spec.qty,
                proceeds_unit_price=spec.proceeds_unit_price,
                proceeds_currency=spec.proceeds_currency,
                realized_pnl_irr=spec.realized_irr,
                realized_pnl_usd=spec.realized_usd,
                consumed_at=spec.consumed_at,
            )
        )
    db.flush()


def _delete_existing(db: Session, user_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    lot_ids = select(Lot.id).where(Lot.user_id == user_id, Lot.asset_id == asset_id)
    db.execute(
        delete(LotConsumption).where(LotConsumption.lot_id.in_(lot_ids))
    )
    db.execute(delete(Lot).where(Lot.user_id == user_id, Lot.asset_id == asset_id))
    db.flush()


def _acquisition_cost(
    db: Session, user_id: uuid.UUID, asset: Asset, txn: Transaction, leg: TransactionLeg
) -> tuple[Decimal | None, str | None, Decimal | None, Decimal | None]:
    """(unit_cost_native, cost_currency, unit_cost_irr, unit_cost_usd) for a buy/
    deposit/income leg, snapshotting FX at the acquisition date."""
    date = txn.occurred_at
    if asset.asset_class is AssetClass.fiat:
        # base currency costs its nominal value in its own currency (zero P&L
        # there); the other reporting currency comes from acquisition FX.
        return (
            Decimal(1),
            asset.symbol,
            valuation.to_irr(db, user_id, Decimal(1), asset.symbol, date),
            valuation.to_usd(db, user_id, Decimal(1), asset.symbol, date),
        )
    if leg.unit_price is not None:
        # trade buy price, or manual cost-basis override on deposit/income
        ccy = leg.price_currency or asset.quote_currency
        return (
            leg.unit_price,
            ccy,
            valuation.to_irr(db, user_id, leg.unit_price, ccy, date),
            valuation.to_usd(db, user_id, leg.unit_price, ccy, date),
        )
    # deposit/income without override -> price snapshot
    native = valuation.nearest_price(db, user_id, asset.id, asset.quote_currency, date)
    return (
        native,
        asset.quote_currency,
        valuation.market_unit_value(db, user_id, asset, valuation.IRR, date),
        valuation.market_unit_value(db, user_id, asset, valuation.USD, date),
    )


def _make_increase_lot(
    db: Session,
    user_id: uuid.UUID,
    asset: Asset,
    txn: Transaction,
    leg: TransactionLeg,
    qty: Decimal,
    account_id: uuid.UUID,
) -> Lot:
    native, ccy, irr, usd = _acquisition_cost(db, user_id, asset, txn, leg)
    return Lot(
        user_id=user_id,
        account_id=account_id,
        asset_id=asset.id,
        source_leg_id=leg.id,
        original_qty=qty,
        remaining_qty=qty,
        unit_cost=native,
        cost_currency=ccy,
        unit_cost_irr=irr,
        unit_cost_usd=usd,
        acquired_at=txn.occurred_at,
    )


def _consume(
    open_lots: list[Lot], qty: Decimal, asset: Asset, txn: Transaction
) -> list[tuple[Lot, Decimal]]:
    """Reduce open lots by `qty` (positive) in strategy order. Returns the
    (lot, qty_taken) segments consumed."""
    available = [lot for lot in open_lots if lot.remaining_qty > 0]
    segments: list[tuple[Lot, Decimal]] = []
    remaining = qty
    for lot in DEFAULT_STRATEGY.order(available):
        if remaining <= 0:
            break
        take = min(remaining, lot.remaining_qty)
        lot.remaining_qty -= take
        segments.append((lot, take))
        remaining -= take
    if remaining > 0:
        # Should not happen: the non-negative balance invariant guarantees cover.
        raise unprocessable(
            "Cost-basis reconstruction failed: insufficient lots",
            details={
                "asset_id": str(asset.id),
                "occurred_at": txn.occurred_at.isoformat(),
                "shortfall": str(remaining),
            },
        )
    return segments


def _realize(
    db: Session,
    user_id: uuid.UUID,
    asset: Asset,
    txn: Transaction,
    leg: TransactionLeg,
    segments: list[tuple[Lot, Decimal]],
) -> list[_ConsumptionSpec]:
    date = txn.occurred_at
    proceeds = leg.unit_price
    pccy = leg.price_currency or (asset.symbol if asset.asset_class is AssetClass.fiat else asset.quote_currency)
    proceeds_irr = valuation.to_irr(db, user_id, proceeds, pccy, date) if proceeds is not None else None
    proceeds_usd = valuation.to_usd(db, user_id, proceeds, pccy, date) if proceeds is not None else None

    specs = []
    for lot, take in segments:
        r_irr = (
            (proceeds_irr - lot.unit_cost_irr) * take
            if proceeds_irr is not None and lot.unit_cost_irr is not None
            else None
        )
        r_usd = (
            (proceeds_usd - lot.unit_cost_usd) * take
            if proceeds_usd is not None and lot.unit_cost_usd is not None
            else None
        )
        specs.append(
            _ConsumptionSpec(
                lot=lot,
                sell_leg_id=leg.id,
                qty=take,
                proceeds_unit_price=proceeds,
                proceeds_currency=pccy,
                realized_irr=r_irr,
                realized_usd=r_usd,
                consumed_at=date,
            )
        )
    return specs


def _replay_transfer(
    db: Session,
    user_id: uuid.UUID,
    asset: Asset,
    txn: Transaction,
    legs_here: list[TransactionLeg],
    open_by_account: dict[uuid.UUID, list[Lot]],
    new_lots: list[Lot],
) -> None:
    """Carry cost basis from source to destination; no realized P&L. The fee
    (sent > received) raises the per-unit cost of the carried lots."""
    out_leg = next(leg for leg in legs_here if leg.quantity < 0)
    in_leg = next(leg for leg in legs_here if leg.quantity > 0)
    sent = -out_leg.quantity
    received = in_leg.quantity
    if sent <= 0:
        return
    ratio = received / sent  # <= 1 (fee), preserves total cost across fewer units

    segments = _consume(open_by_account.get(out_leg.account_id, []), sent, asset, txn)
    for lot, take in segments:
        dest_qty = take * ratio
        if dest_qty == 0:
            continue
        dest = Lot(
            user_id=user_id,
            account_id=in_leg.account_id,
            asset_id=asset.id,
            source_leg_id=in_leg.id,
            original_qty=dest_qty,
            remaining_qty=dest_qty,
            unit_cost=(lot.unit_cost / ratio) if lot.unit_cost is not None else None,
            cost_currency=lot.cost_currency,
            unit_cost_irr=(lot.unit_cost_irr / ratio) if lot.unit_cost_irr is not None else None,
            unit_cost_usd=(lot.unit_cost_usd / ratio) if lot.unit_cost_usd is not None else None,
            acquired_at=lot.acquired_at,  # preserve FIFO ordering of the carried cost
        )
        open_by_account.setdefault(in_leg.account_id, []).append(dest)
        new_lots.append(dest)


def rebuild_for_assets(
    db: Session, user_id: uuid.UUID, asset_ids: set[uuid.UUID]
) -> None:
    for asset_id in asset_ids:
        rebuild(db, user_id, asset_id)
