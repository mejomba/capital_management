import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, SoftDeleteMixin, UUIDPKMixin


class GoalType(str, enum.Enum):
    target_net_worth = "target_net_worth"
    target_return = "target_return"
    target_allocation = "target_allocation"
    custom = "custom"


class GoalStatus(str, enum.Enum):
    active = "active"
    achieved = "achieved"
    archived = "archived"


class Goal(UUIDPKMixin, SoftDeleteMixin, Base):
    """A financial goal. Progress is *derived* (not stored)."""

    __tablename__ = "goal"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    type: Mapped[GoalType] = mapped_column(
        SAEnum(GoalType, name="goal_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_allocation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[GoalStatus] = mapped_column(
        SAEnum(GoalStatus, name="goal_status"), nullable=False, default=GoalStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
