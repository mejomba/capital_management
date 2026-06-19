import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class TransactionType(str, enum.Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    trade = "trade"
    transfer = "transfer"
    income = "income"
    fee = "fee"
    expense = "expense"


class TransactionStatus(str, enum.Enum):
    active = "active"
    reversed = "reversed"


class Transaction(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "transaction"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id"), index=True, nullable=False
    )
    type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, name="transaction_status"),
        nullable=False,
        default=TransactionStatus.active,
    )
    reversal_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transaction.id"), nullable=True
    )

    legs: Mapped[list["TransactionLeg"]] = relationship(
        "TransactionLeg",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="TransactionLeg.id",
    )


from app.models.transaction_leg import TransactionLeg  # noqa: E402  (resolve relationship)
