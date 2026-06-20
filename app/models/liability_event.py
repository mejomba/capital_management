import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, UUIDPKMixin


class LiabilityEventType(str, enum.Enum):
    disbursement = "disbursement"
    repayment = "repayment"
    interest = "interest"


class LiabilityEvent(UUIDPKMixin, Base):
    """An immutable movement on a liability.

    Balance derivation (no double-counting of interest):
      - interest is recognised ONLY via `interest` events -> interest_unpaid.
      - a `repayment` settles existing balances via its components:
          principal_component  reduces principal_outstanding
          interest_component   reduces interest_unpaid
        `amount` itself is never subtracted from principal directly; it only acts
        as a checksum (principal_component + interest_component == amount).
    """

    __tablename__ = "liability_event"

    liability_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("liability.id"), index=True, nullable=False
    )
    type: Mapped[LiabilityEventType] = mapped_column(
        SAEnum(LiabilityEventType, name="liability_event_type"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    principal_component: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    interest_component: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    liability: Mapped["Liability"] = relationship(back_populates="events")
