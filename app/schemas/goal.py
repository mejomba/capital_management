import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.goal import GoalStatus, GoalType
from app.schemas.common import MoneyStr, ORMModel


class GoalCreate(BaseModel):
    type: GoalType
    title: str = Field(min_length=1, max_length=255)
    target_value: Decimal | None = None
    currency: str | None = Field(default=None, max_length=16)
    target_allocation: dict[str, Any] | None = None
    target_date: date | None = None
    status: GoalStatus | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    target_value: Decimal | None = None
    currency: str | None = Field(default=None, max_length=16)
    target_allocation: dict[str, Any] | None = None
    target_date: date | None = None
    status: GoalStatus | None = None


class GoalOut(ORMModel):
    id: uuid.UUID
    type: GoalType
    title: str
    target_value: MoneyStr | None = None
    currency: str | None = None
    target_allocation: dict[str, Any] | None = Field(
        default=None, validation_alias="target_allocation_json"
    )
    target_date: date | None = None
    status: GoalStatus
    created_at: datetime


class GoalDetailOut(GoalOut):
    progress: dict[str, Any]
