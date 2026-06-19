import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, page_params
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.schemas.common import Page
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=Page[AccountOut])
def list_accounts(
    current_user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[AccountOut]:
    items, total = account_service.list_accounts(db, current_user.id, params)
    return Page[AccountOut](
        items=[AccountOut.model_validate(a) for a in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    data: AccountCreate, current_user: CurrentUser, db: DbSession
) -> AccountOut:
    account = account_service.create_account(db, current_user.id, data)
    return AccountOut.model_validate(account)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> AccountOut:
    account = account_service.get_account(db, current_user.id, account_id)
    return AccountOut.model_validate(account)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> AccountOut:
    account = account_service.update_account(db, current_user.id, account_id, data)
    return AccountOut.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    account_service.delete_account(db, current_user.id, account_id)
