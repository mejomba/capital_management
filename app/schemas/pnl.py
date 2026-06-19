from app.schemas.common import MoneyStr, ORMModel


class PnlAmount(ORMModel):
    irr: MoneyStr | None = None
    usd: MoneyStr | None = None


class PnlGroup(ORMModel):
    key: str
    realized_irr: MoneyStr | None = None
    realized_usd: MoneyStr | None = None
    unrealized_irr: MoneyStr | None = None
    unrealized_usd: MoneyStr | None = None


class PnlOut(ORMModel):
    realized: PnlAmount
    unrealized: PnlAmount
    group_by: str | None = None
    groups: list[PnlGroup]
