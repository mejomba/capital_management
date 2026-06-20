import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, UUIDPKMixin


class InflationRate(UUIDPKMixin, Base):
    """A monthly inflation rate (decimal fraction, e.g. 0.025 = 2.5%/month).
    Unique per (user, year, month) so POST upserts."""

    __tablename__ = "inflation_rate"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "period_year", "period_month", name="uq_inflation_user_period"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Money, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
