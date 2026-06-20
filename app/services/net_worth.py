"""Live net-worth computation: assets (valued holdings) minus liabilities,
in both IRR and USD. Fully derived — the basis for daily snapshots."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services import holdings as holdings_service
from app.services import liabilities as liabilities_service
from app.services import valuation


def _sum(values) -> Decimal:
    return sum((v for v in values if v is not None), Decimal(0))


def compute_live(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> dict:
    eff = as_of or datetime.now(timezone.utc)

    rows = holdings_service.valued_holdings(db, user_id, eff)
    total_assets_irr = _sum(r["value_irr"] for r in rows)
    total_assets_usd = _sum(r["value_usd"] for r in rows)

    unvalued_assets = [
        {"asset_id": str(r["asset_id"]), "symbol": r["symbol"], "quantity": str(r["quantity"])}
        for r in rows
        if r["value_irr"] is None and r["value_usd"] is None
    ]

    by_class = _by_class(db, user_id, eff)

    by_account: dict[str, dict] = {}
    for r in rows:
        acc = by_account.setdefault(
            str(r["account_id"]), {"account_id": str(r["account_id"]), "value_irr": Decimal(0), "value_usd": Decimal(0)}
        )
        if r["value_irr"] is not None:
            acc["value_irr"] += r["value_irr"]
        if r["value_usd"] is not None:
            acc["value_usd"] += r["value_usd"]
    by_account_list = [
        {"account_id": a["account_id"], "value_irr": str(a["value_irr"]), "value_usd": str(a["value_usd"])}
        for a in by_account.values()
    ]

    liab_irr = Decimal(0)
    liab_usd = Decimal(0)
    liabilities_breakdown = []
    unvalued_liabilities = []
    for liability, bal in liabilities_service.outstanding_for_all(db, user_id, eff):
        total = bal["total_outstanding"]
        v_irr = valuation.convert(db, user_id, total, liability.currency, valuation.IRR, eff)
        v_usd = valuation.convert(db, user_id, total, liability.currency, valuation.USD, eff)
        if v_irr is not None:
            liab_irr += v_irr
        if v_usd is not None:
            liab_usd += v_usd
        if v_irr is None and v_usd is None:
            unvalued_liabilities.append({"liability_id": str(liability.id), "name": liability.name})
        liabilities_breakdown.append(
            {
                "liability_id": str(liability.id),
                "name": liability.name,
                "currency": liability.currency,
                "total_outstanding": str(total),
                "value_irr": str(v_irr) if v_irr is not None else None,
                "value_usd": str(v_usd) if v_usd is not None else None,
            }
        )

    return {
        "total_assets_irr": total_assets_irr,
        "total_assets_usd": total_assets_usd,
        "total_liabilities_irr": liab_irr,
        "total_liabilities_usd": liab_usd,
        "net_worth_irr": total_assets_irr - liab_irr,
        "net_worth_usd": total_assets_usd - liab_usd,
        "breakdown": {
            "by_class": by_class,
            "by_account": by_account_list,
            "liabilities": liabilities_breakdown,
            "unvalued_assets": unvalued_assets,
            "unvalued_liabilities": unvalued_liabilities,
        },
    }


def _by_class(db: Session, user_id: uuid.UUID, eff: datetime) -> list[dict]:
    out = []
    for cls in holdings_service.valued_by_class(db, user_id, eff):
        v_irr = _sum(i["value_irr"] for i in cls["items"])
        v_usd = _sum(i["value_usd"] for i in cls["items"])
        out.append(
            {
                "asset_class": cls["asset_class"].value,
                "value_irr": str(v_irr),
                "value_usd": str(v_usd),
            }
        )
    return out
