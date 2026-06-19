import uuid

from app.models.asset import AssetClass
from app.schemas.common import MoneyStr, ORMModel


class HoldingOut(ORMModel):
    account_id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    quantity: MoneyStr


class HoldingByAssetOut(ORMModel):
    asset_id: uuid.UUID
    symbol: str
    asset_class: AssetClass
    quantity: MoneyStr


class AssetQuantity(ORMModel):
    asset_id: uuid.UUID
    symbol: str
    quantity: MoneyStr


class HoldingByClassOut(ORMModel):
    # Quantities of different assets cannot be summed into one number without
    # valuation (M3), so a class groups its per-asset holdings.
    asset_class: AssetClass
    items: list[AssetQuantity]
