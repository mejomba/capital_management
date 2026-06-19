import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import MoneyStr, ORMModel


class PriceCreate(BaseModel):
    asset_id: uuid.UUID
    quote_currency: str = Field(min_length=1, max_length=16)
    price: Decimal = Field(ge=0)
    as_of: date
    source: str = Field(default="manual", max_length=16)


class PriceOut(ORMModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    quote_currency: str
    price: MoneyStr
    as_of: date
    source: str
    created_at: datetime


class FxOut(BaseModel):
    from_currency: str = Field(serialization_alias="from")
    to_currency: str = Field(serialization_alias="to")
    as_of: date
    rate: MoneyStr | None = None
