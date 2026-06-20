import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.assumptions import DisplayCurrency, HurdleMode
from app.schemas.common import MoneyStr, ORMModel


class AssumptionsUpdate(BaseModel):
    display_currency: DisplayCurrency = DisplayCurrency.both
    hurdle_mode: HurdleMode = HurdleMode.inflation
    hurdle_fixed_rate: Decimal | None = None
    growth_assumptions: dict[str, Any] | None = None


class AssumptionsOut(ORMModel):
    id: uuid.UUID | None = None
    display_currency: DisplayCurrency
    hurdle_mode: HurdleMode
    hurdle_fixed_rate: MoneyStr | None = None
    growth_assumptions: dict[str, Any] = Field(
        default_factory=dict, validation_alias="growth_assumptions_json"
    )
    updated_at: datetime | None = None
