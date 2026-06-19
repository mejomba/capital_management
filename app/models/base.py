"""Declarative base, shared mixins, and the canonical money column type.

Per CLAUDE.md §4: every monetary / asset-quantity value is ``Decimal`` in Python
and ``NUMERIC(38,18)`` in the database. ``Money`` is the single source of truth
for that column type so later milestones (transactions, prices, lots) stay
consistent. UTC-aware timestamps everywhere (CLAUDE.md §10).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Canonical monetary / quantity column type — never use plain Float anywhere.
Money = Numeric(38, 18, asdecimal=True)


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
