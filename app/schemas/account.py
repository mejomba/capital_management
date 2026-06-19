import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.account import AccountType
from app.schemas.common import ORMModel


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: AccountType
    currency_hint: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=1024)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: AccountType | None = None
    currency_hint: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=1024)


class AccountOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: AccountType
    currency_hint: str | None = None
    note: str | None = None
    created_at: datetime
