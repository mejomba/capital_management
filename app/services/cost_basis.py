"""Swappable cost-basis strategy. FIFO today; WAC/LIFO later by changing
DEFAULT_STRATEGY only."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class OpenLot:
    """A mutable, in-memory open lot used during replay."""

    lot_id: object  # uuid.UUID of the persisted Lot (or transient marker)
    remaining_qty: Decimal
    unit_cost_irr: Decimal | None
    unit_cost_usd: Decimal | None
    unit_cost: Decimal | None
    cost_currency: str | None
    acquired_at: object  # datetime


class CostBasisStrategy(Protocol):
    def order(self, lots: list[OpenLot]) -> list[OpenLot]:
        """Return the lots in the order they should be consumed."""
        ...


class FIFOStrategy:
    """First in, first out — by acquisition time."""

    def order(self, lots: list[OpenLot]) -> list[OpenLot]:
        return sorted(lots, key=lambda lot_obj: lot_obj.acquired_at)


DEFAULT_STRATEGY: CostBasisStrategy = FIFOStrategy()
