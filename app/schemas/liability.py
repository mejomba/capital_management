import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.liability import LiabilityType
from app.models.liability_event import LiabilityEventType
from app.schemas.common import MoneyStr, ORMModel


class LiabilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: LiabilityType
    principal: Decimal = Field(ge=0)
    currency: str = Field(min_length=1, max_length=16)
    interest_rate: Decimal | None = None
    start_date: date
    term_months: int | None = Field(default=None, ge=0)
    schedule: dict | None = None


class LiabilityEventCreate(BaseModel):
    type: LiabilityEventType
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=1, max_length=16)
    occurred_at: datetime
    principal_component: Decimal | None = Field(default=None, ge=0)
    interest_component: Decimal | None = Field(default=None, ge=0)


class LiabilityEventOut(ORMModel):
    id: uuid.UUID
    liability_id: uuid.UUID
    type: LiabilityEventType
    amount: MoneyStr
    currency: str
    occurred_at: datetime
    principal_component: MoneyStr | None = None
    interest_component: MoneyStr | None = None
    created_at: datetime


class LiabilityBalance(BaseModel):
    currency: str
    principal_outstanding: MoneyStr
    interest_unpaid: MoneyStr
    total_outstanding: MoneyStr


class LiabilityOut(ORMModel):
    id: uuid.UUID
    name: str
    type: LiabilityType
    principal: MoneyStr
    currency: str
    interest_rate: MoneyStr | None = None
    start_date: date
    term_months: int | None = None
    schedule: dict | None = Field(default=None, validation_alias="schedule_json")
    created_at: datetime
    balance: LiabilityBalance


class LiabilityDetailOut(LiabilityOut):
    events: list[LiabilityEventOut]
