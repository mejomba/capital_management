import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SAEnum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, UUIDPKMixin


class DisplayCurrency(str, enum.Enum):
    irr = "irr"
    usd = "usd"
    both = "both"


class HurdleMode(str, enum.Enum):
    fixed = "fixed"
    inflation = "inflation"
    usd_growth = "usd_growth"


class Assumptions(UUIDPKMixin, Base):
    """Per-user analysis settings: display currency, hurdle definition, and
    assumed annual growth per asset_class (for projections). One row per user."""

    __tablename__ = "assumptions"

    user_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True, nullable=False)
    display_currency: Mapped[DisplayCurrency] = mapped_column(
        SAEnum(DisplayCurrency, name="display_currency"),
        nullable=False,
        default=DisplayCurrency.both,
    )
    hurdle_mode: Mapped[HurdleMode] = mapped_column(
        SAEnum(HurdleMode, name="hurdle_mode"),
        nullable=False,
        default=HurdleMode.inflation,
    )
    hurdle_fixed_rate: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    growth_assumptions_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
