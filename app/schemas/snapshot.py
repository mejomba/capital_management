import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import MoneyStr, ORMModel


class SnapshotOut(ORMModel):
    id: uuid.UUID
    as_of: date
    total_assets_irr: MoneyStr | None = None
    total_assets_usd: MoneyStr | None = None
    total_liabilities_irr: MoneyStr | None = None
    total_liabilities_usd: MoneyStr | None = None
    net_worth_irr: MoneyStr | None = None
    net_worth_usd: MoneyStr | None = None
    breakdown: dict[str, Any] = Field(validation_alias="breakdown_json")
    created_at: datetime


class RebuildRequest(BaseModel):
    date_from: date = Field(validation_alias="from")
    date_to: date = Field(validation_alias="to")


class RebuildResult(BaseModel):
    created: int
    date_from: date = Field(serialization_alias="from")
    date_to: date = Field(serialization_alias="to")


class NetWorthPoint(ORMModel):
    as_of: date
    total_assets_irr: MoneyStr | None = None
    total_assets_usd: MoneyStr | None = None
    total_liabilities_irr: MoneyStr | None = None
    total_liabilities_usd: MoneyStr | None = None
    net_worth_irr: MoneyStr | None = None
    net_worth_usd: MoneyStr | None = None


class NetWorthSeriesOut(BaseModel):
    currency: str
    series: list[NetWorthPoint]
