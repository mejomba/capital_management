import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, page_params
from app.models.transaction import TransactionType
from app.schemas.common import Page
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services import ledger
from app.services.ledger import TxnFilters

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=Page[TransactionOut])
def list_transactions(
    current_user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    type: TransactionType | None = None,
    account_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    date_from: Annotated[datetime | None, Query(alias="from")] = None,
    date_to: Annotated[datetime | None, Query(alias="to")] = None,
    tag: str | None = None,  # reserved: tags arrive in a later milestone
) -> Page[TransactionOut]:
    filters = TxnFilters(
        type=type,
        account_id=account_id,
        asset_id=asset_id,
        date_from=date_from,
        date_to=date_to,
    )
    items, total = ledger.list_transactions(db, current_user.id, filters, params)
    return Page[TransactionOut](
        items=[TransactionOut.model_validate(t) for t in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    current_user: CurrentUser,
    db: DbSession,
    data: Annotated[TransactionCreate, Body()],
) -> TransactionOut:
    txn = ledger.create_transaction(db, current_user.id, data)
    return TransactionOut.model_validate(txn)


@router.get("/{txn_id}", response_model=TransactionOut)
def get_transaction(
    txn_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> TransactionOut:
    txn = ledger.get_transaction(db, current_user.id, txn_id)
    return TransactionOut.model_validate(txn)


@router.post(
    "/{txn_id}/reverse",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def reverse_transaction(
    txn_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> TransactionOut:
    reversal = ledger.reverse_transaction(db, current_user.id, txn_id)
    return TransactionOut.model_validate(reversal)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    txn_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    ledger.delete_transaction(db, current_user.id, txn_id)
