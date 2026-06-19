import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, page_params
from app.schemas.common import Page
from app.schemas.price import FxOut, PriceCreate, PriceOut
from app.services import prices as price_service

router = APIRouter(tags=["prices"])


@router.get("/prices", response_model=Page[PriceOut])
def list_prices(
    current_user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    asset_id: uuid.UUID | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> Page[PriceOut]:
    items, total = price_service.list_prices(
        db, current_user.id, params, asset_id, date_from, date_to
    )
    return Page[PriceOut](
        items=[PriceOut.model_validate(p) for p in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/prices", response_model=PriceOut, status_code=status.HTTP_201_CREATED)
def create_price(
    data: PriceCreate, current_user: CurrentUser, db: DbSession
) -> PriceOut:
    price = price_service.create_price(db, current_user.id, data)
    return PriceOut.model_validate(price)


@router.post(
    "/prices/bulk",
    response_model=list[PriceOut],
    status_code=status.HTTP_201_CREATED,
)
def create_prices_bulk(
    data: list[PriceCreate], current_user: CurrentUser, db: DbSession
) -> list[PriceOut]:
    prices = price_service.create_prices_bulk(db, current_user.id, data)
    return [PriceOut.model_validate(p) for p in prices]


@router.get("/fx", response_model=FxOut)
def get_fx(
    current_user: CurrentUser,
    db: DbSession,
    from_currency: Annotated[str, Query(alias="from")] = "USD",
    to_currency: Annotated[str, Query(alias="to")] = "IRR",
    as_of: date | None = None,
) -> FxOut:
    target_date = as_of or date.today()
    rate = price_service.fx_rate(
        db, current_user.id, from_currency, to_currency, target_date
    )
    return FxOut(
        from_currency=from_currency,
        to_currency=to_currency,
        as_of=target_date,
        rate=rate,
    )
