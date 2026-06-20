from pydantic import BaseModel


class ProjectionPoint(BaseModel):
    month: int
    net_worth_irr: str
    net_worth_usd: str | None = None


class ProjectionOut(BaseModel):
    horizon_months: int
    monthly_contribution: str
    scenarios: dict[str, list[ProjectionPoint]]
