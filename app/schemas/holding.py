import uuid

from app.models.asset import AssetClass
from app.schemas.common import MoneyStr, ORMModel


class HoldingOut(ORMModel):
    account_id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    quantity: MoneyStr
    value_irr: MoneyStr | None = None
    value_usd: MoneyStr | None = None
    unrealized_pnl_irr: MoneyStr | None = None
    unrealized_pnl_usd: MoneyStr | None = None


class HoldingByAssetOut(ORMModel):
    asset_id: uuid.UUID
    symbol: str
    asset_class: AssetClass
    quantity: MoneyStr
    value_irr: MoneyStr | None = None
    value_usd: MoneyStr | None = None
    unrealized_pnl_irr: MoneyStr | None = None
    unrealized_pnl_usd: MoneyStr | None = None


class AssetQuantity(ORMModel):
    asset_id: uuid.UUID
    symbol: str
    quantity: MoneyStr
    value_irr: MoneyStr | None = None
    value_usd: MoneyStr | None = None
    unrealized_pnl_irr: MoneyStr | None = None
    unrealized_pnl_usd: MoneyStr | None = None


class HoldingByClassOut(ORMModel):
    asset_class: AssetClass
    items: list[AssetQuantity]
