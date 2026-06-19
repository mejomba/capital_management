import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.asset import AssetClass
from app.schemas.common import ORMModel


class AssetCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    asset_class: AssetClass
    unit: str = Field(min_length=1, max_length=32)
    quote_currency: str = Field(min_length=1, max_length=16)


class AssetUpdate(BaseModel):
    symbol: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_class: AssetClass | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    quote_currency: str | None = Field(default=None, min_length=1, max_length=16)
    is_active: bool | None = None


class AssetOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    symbol: str
    name: str
    asset_class: AssetClass
    unit: str
    quote_currency: str
    is_active: bool
    created_at: datetime
