from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PerfMetrics(BaseModel):
    xirr: str | None = None
    twr: str | None = None
    nominal: str | None = None
    real: str | None = None


class PerformanceOut(ORMModel):
    from_dt: datetime = Field(serialization_alias="from")
    to_dt: datetime = Field(serialization_alias="to")
    irr: PerfMetrics
    usd: PerfMetrics
    inflation_cumulative: str
    usd_based: str | None = None


class InflationComparisonOut(ORMModel):
    from_dt: datetime = Field(serialization_alias="from")
    to_dt: datetime = Field(serialization_alias="to")
    nominal_irr: str | None = None
    real_irr: str | None = None
    usd_based: str | None = None
    inflation: str
    hurdle: dict[str, Any]
    beats_inflation: bool | None = None
    beats_hurdle: bool | None = None
