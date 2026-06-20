import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, page_params
from app.schemas.common import Page
from app.schemas.liability import (
    LiabilityBalance,
    LiabilityCreate,
    LiabilityDetailOut,
    LiabilityEventCreate,
    LiabilityEventOut,
    LiabilityOut,
)
from app.services import liabilities as liability_service

router = APIRouter(tags=["liabilities"])


def _with_balance(liability) -> LiabilityOut:
    liability.balance = LiabilityBalance(**liability_service.outstanding(liability))
    return LiabilityOut.model_validate(liability)


@router.get("/liabilities", response_model=Page[LiabilityOut])
def list_liabilities(
    current_user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[LiabilityOut]:
    items, total = liability_service.list_liabilities(db, current_user.id, params)
    return Page[LiabilityOut](
        items=[_with_balance(item) for item in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/liabilities", response_model=LiabilityOut, status_code=status.HTTP_201_CREATED)
def create_liability(
    data: LiabilityCreate, current_user: CurrentUser, db: DbSession
) -> LiabilityOut:
    liability = liability_service.create_liability(db, current_user.id, data)
    return _with_balance(liability)


@router.get("/liabilities/{liability_id}", response_model=LiabilityDetailOut)
def get_liability(
    liability_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> LiabilityDetailOut:
    liability = liability_service.get_liability(db, current_user.id, liability_id)
    liability.balance = LiabilityBalance(**liability_service.outstanding(liability))
    return LiabilityDetailOut.model_validate(liability)


@router.post(
    "/liabilities/{liability_id}/events",
    response_model=LiabilityEventOut,
    status_code=status.HTTP_201_CREATED,
)
def add_event(
    liability_id: uuid.UUID,
    data: LiabilityEventCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> LiabilityEventOut:
    event = liability_service.add_event(db, current_user.id, liability_id, data)
    return LiabilityEventOut.model_validate(event)
