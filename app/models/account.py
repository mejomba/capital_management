import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class AccountType(str, enum.Enum):
    bank = "bank"
    exchange = "exchange"
    brokerage = "brokerage"
    wallet = "wallet"
    physical = "physical"
    property = "property"
    other = "other"


class Account(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "account"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type"), nullable=False
    )
    currency_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
