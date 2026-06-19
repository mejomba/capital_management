import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, UUIDPKMixin


class TransactionLeg(UUIDPKMixin, Base):
    __tablename__ = "transaction_leg"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transaction.id"), index=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account.id"), index=True, nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset.id"), index=True, nullable=False
    )
    # Signed: negative = leaves the account, positive = enters the account.
    quantity: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    fee_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)

    transaction: Mapped["Transaction"] = relationship(  # noqa: F821
        "Transaction", back_populates="legs"
    )
