import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import MoneyStr, ORMModel


class InflationRateCreate(BaseModel):
    period_year: int = Field(ge=1900, le=3000)
    period_month: int = Field(ge=1, le=12)
    rate: Decimal
    source: str = Field(default="manual", max_length=64)


class InflationRateOut(ORMModel):
    id: uuid.UUID
    period_year: int
    period_month: int
    rate: MoneyStr
    source: str
    created_at: datetime
