import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, UUIDPKMixin


class Lot(UUIDPKMixin, Base):
    """FIFO cost-basis lot. A materialised projection: deterministically rebuilt
    from active transactions, never delta-mutated. Cost columns are nullable
    when the acquisition could not be valued (missing price/FX)."""

    __tablename__ = "lot"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id"), index=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account.id"), index=True, nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset.id"), index=True, nullable=False
    )
    source_leg_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transaction_leg.id"), nullable=False
    )
    original_qty: Mapped[Decimal] = mapped_column(Money, nullable=False)
    remaining_qty: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_cost_irr: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    unit_cost_usd: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
