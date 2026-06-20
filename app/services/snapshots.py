"""Portfolio snapshots: a daily, fully-derived net-worth record.

Always recomputable from transactions + prices (CLAUDE.md §3). Upserted on
(user, as_of) so rebuilds are idempotent. Days without a price for an asset use
the nearest earlier price (valuation rule); an asset with no price at all is
flagged unvalued rather than erroring, so the net-worth chart has no holes.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.user import User
from app.services import net_worth


def _end_of_day(as_of: date) -> datetime:
    return datetime.combine(as_of, time.max, tzinfo=timezone.utc)


def build_snapshot(
    db: Session, user_id: uuid.UUID, as_of: date, commit: bool = True
) -> PortfolioSnapshot:
    """Compute and upsert the snapshot for (user, as_of)."""
    nw = net_worth.compute_live(db, user_id, _end_of_day(as_of))

    snapshot = db.scalar(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.as_of == as_of,
        )
    )
    if snapshot is None:
        snapshot = PortfolioSnapshot(user_id=user_id, as_of=as_of)
        db.add(snapshot)

    snapshot.total_assets_irr = nw["total_assets_irr"]
    snapshot.total_assets_usd = nw["total_assets_usd"]
    snapshot.total_liabilities_irr = nw["total_liabilities_irr"]
    snapshot.total_liabilities_usd = nw["total_liabilities_usd"]
    snapshot.net_worth_irr = nw["net_worth_irr"]
    snapshot.net_worth_usd = nw["net_worth_usd"]
    snapshot.breakdown_json = nw["breakdown"]

    db.flush()
    if commit:
        db.commit()
        db.refresh(snapshot)
    return snapshot


def backfill(
    db: Session, user_id: uuid.UUID, date_from: date, date_to: date
) -> int:
    """Rebuild snapshots for every day in [date_from, date_to]. Idempotent."""
    if date_to < date_from:
        return 0
    day = date_from
    count = 0
    while day <= date_to:
        build_snapshot(db, user_id, day, commit=False)
        count += 1
        day += timedelta(days=1)
    db.commit()
    return count


def list_snapshots(
    db: Session,
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[PortfolioSnapshot]:
    conds = [PortfolioSnapshot.user_id == user_id]
    if date_from is not None:
        conds.append(PortfolioSnapshot.as_of >= date_from)
    if date_to is not None:
        conds.append(PortfolioSnapshot.as_of <= date_to)
    return list(
        db.scalars(
            select(PortfolioSnapshot).where(*conds).order_by(PortfolioSnapshot.as_of)
        )
    )


def run_daily_snapshots(session_factory, as_of: date | None = None) -> int:
    """Build today's snapshot for every active user. Used by the scheduler."""
    target = as_of or datetime.now(timezone.utc).date()
    built = 0
    db: Session = session_factory()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.deleted_at.is_(None))))
        for uid in user_ids:
            build_snapshot(db, uid, target, commit=False)
            built += 1
        db.commit()
    finally:
        db.close()
    return built
