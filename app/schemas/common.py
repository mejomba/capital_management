from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")

# Per CLAUDE.md §4: monetary values are serialised as strings in the API so no
# precision is lost. Money-bearing schemas (from M2 onward) use this type.
MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    """Uniform error envelope (documented in OpenAPI)."""

    error: ErrorBody
