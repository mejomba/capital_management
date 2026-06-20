from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class RebalanceItem(BaseModel):
    asset_class: str
    current_value: str
    target_value: str
    action: str
    amount: str
    delta: str


class AllocationOut(ORMModel):
    as_of: datetime
    currency: str
    total_value: str
    current: dict[str, str]
    target: dict[str, str]
    drift: dict[str, str]
    rebalance: list[RebalanceItem]
