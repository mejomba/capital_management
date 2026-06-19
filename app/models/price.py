import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, UUIDPKMixin


class Price(UUIDPKMixin, Base):
    """Manually entered price snapshot. USD/IRR FX is just a price row with
    asset=USD, quote_currency=IRR (DATA_MODEL.md)."""

    __tablename__ = "price"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id"), index=True, nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset.id"), index=True, nullable=False
    )
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
