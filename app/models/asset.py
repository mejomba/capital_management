import enum
import uuid

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class AssetClass(str, enum.Enum):
    equity = "equity"
    fund = "fund"
    crypto = "crypto"
    metal = "metal"
    forex = "forex"
    real_estate = "real_estate"
    fiat = "fiat"
    other = "other"


class Asset(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "asset"

    # NULL user_id => system / shared asset (visible to everyone).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id"), index=True, nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_class: Mapped[AssetClass] = mapped_column(
        SAEnum(AssetClass, name="asset_class"), nullable=False
    )
    # unit: gram | share | coin | unit | <currency_code>
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
