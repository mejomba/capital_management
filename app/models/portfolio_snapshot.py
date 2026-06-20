import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, UUIDPKMixin


class PortfolioSnapshot(UUIDPKMixin, Base):
    """A daily, fully-derived net-worth snapshot. Unique per (user, as_of) so
    rebuilds upsert rather than duplicate (idempotent / reconcilable)."""

    __tablename__ = "portfolio_snapshot"
    __table_args__ = (
        UniqueConstraint("user_id", "as_of", name="uq_snapshot_user_as_of"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_assets_irr: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    total_assets_usd: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    total_liabilities_irr: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    total_liabilities_usd: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    net_worth_irr: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    net_worth_usd: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    breakdown_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
