import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.models.transaction import TransactionStatus, TransactionType
from app.schemas.common import MoneyStr, ORMModel

# --- input -----------------------------------------------------------------

PositiveQty = Annotated[Decimal, Field(gt=0)]


class LegIn(BaseModel):
    account_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal  # signed; validated != 0 in the service
    unit_price: Decimal | None = Field(default=None, ge=0)
    price_currency: str | None = Field(default=None, max_length=16)


class _SingleLegBase(BaseModel):
    occurred_at: datetime
    account_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: PositiveQty  # magnitude; sign is implied by the transaction type
    unit_price: Decimal | None = Field(default=None, ge=0)
    price_currency: str | None = Field(default=None, max_length=16)
    fee: Decimal | None = Field(default=None, ge=0)
    fee_currency: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=1024)


class _MultiLegBase(BaseModel):
    occurred_at: datetime
    legs: list[LegIn] = Field(min_length=2, max_length=2)
    fee: Decimal | None = Field(default=None, ge=0)
    fee_currency: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=1024)


class DepositCreate(_SingleLegBase):
    type: Literal[TransactionType.deposit] = TransactionType.deposit


class WithdrawalCreate(_SingleLegBase):
    type: Literal[TransactionType.withdrawal] = TransactionType.withdrawal


class IncomeCreate(_SingleLegBase):
    type: Literal[TransactionType.income] = TransactionType.income


class FeeCreate(_SingleLegBase):
    type: Literal[TransactionType.fee] = TransactionType.fee


class ExpenseCreate(_SingleLegBase):
    type: Literal[TransactionType.expense] = TransactionType.expense


class TradeCreate(_MultiLegBase):
    type: Literal[TransactionType.trade] = TransactionType.trade


class TransferCreate(_MultiLegBase):
    type: Literal[TransactionType.transfer] = TransactionType.transfer


TransactionCreate = Annotated[
    Union[
        DepositCreate,
        WithdrawalCreate,
        IncomeCreate,
        FeeCreate,
        ExpenseCreate,
        TradeCreate,
        TransferCreate,
    ],
    Field(discriminator="type"),
]

# --- output ----------------------------------------------------------------


class LegOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: MoneyStr
    unit_price: MoneyStr | None = None
    price_currency: str | None = None
    fee: MoneyStr | None = None
    fee_currency: str | None = None


class TransactionOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: TransactionType
    occurred_at: datetime
    note: str | None = None
    status: TransactionStatus
    reversal_of: uuid.UUID | None = None
    created_at: datetime
    legs: list[LegOut]
