import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, SoftDeleteMixin, UUIDPKMixin


class LiabilityType(str, enum.Enum):
    loan = "loan"
    mortgage = "mortgage"
    installment = "installment"
    credit = "credit"
    other = "other"


class Liability(UUIDPKMixin, SoftDeleteMixin, Base):
    """A debt. Its outstanding balance is *derived* from liability_event rows
    (DATA_MODEL.md), never stored. schedule_json is kept for future use only."""

    __tablename__ = "liability"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[LiabilityType] = mapped_column(
        SAEnum(LiabilityType, name="liability_type"), nullable=False
    )
    principal: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    interest_rate: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    events: Mapped[list["LiabilityEvent"]] = relationship(
        back_populates="liability", order_by="LiabilityEvent.occurred_at"
    )
