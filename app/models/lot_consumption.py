import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, UUIDPKMixin


class LotConsumption(UUIDPKMixin, Base):
    """A FIFO consumption of a lot by a trade sell leg, with dual-currency
    realized P&L. Materialised projection, rebuilt with its lots."""

    __tablename__ = "lot_consumption"

    lot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lot.id"), index=True, nullable=False
    )
    sell_leg_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transaction_leg.id"), nullable=False
    )
    qty_consumed: Mapped[Decimal] = mapped_column(Money, nullable=False)
    proceeds_unit_price: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    proceeds_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    realized_pnl_irr: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    realized_pnl_usd: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
