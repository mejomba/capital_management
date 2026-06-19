"""seed system assets (user_id = NULL)

Revision ID: 0002_seed_system_assets
Revises: 0001_initial
Create Date: 2026-06-19
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_system_assets"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# symbol, name, asset_class, unit, quote_currency
SYSTEM_ASSETS = [
    ("IRR", "Iranian Rial", "fiat", "IRR", "IRR"),
    ("USD", "US Dollar", "fiat", "USD", "IRR"),
    ("EUR", "Euro", "fiat", "EUR", "IRR"),
    ("BTC", "Bitcoin", "crypto", "coin", "USD"),
    ("ETH", "Ethereum", "crypto", "coin", "USD"),
    ("XAU", "Gold", "metal", "gram", "IRR"),
    ("XAG", "Silver", "metal", "gram", "IRR"),
]


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent: only insert a system asset if its symbol is not already present
    # as a system asset (user_id IS NULL).
    insert_sql = sa.text(
        """
        INSERT INTO asset (id, user_id, symbol, name, asset_class, unit,
                           quote_currency, is_active, created_at)
        SELECT CAST(:id AS uuid), NULL, CAST(:symbol AS varchar),
               CAST(:name AS varchar), CAST(:asset_class AS asset_class),
               CAST(:unit AS varchar), CAST(:quote_currency AS varchar),
               TRUE, now()
        WHERE NOT EXISTS (
            SELECT 1 FROM asset
            WHERE symbol = CAST(:symbol AS varchar) AND user_id IS NULL
        )
        """
    )
    for symbol, name, asset_class, unit, quote_currency in SYSTEM_ASSETS:
        bind.execute(
            insert_sql,
            {
                "id": uuid.uuid4(),
                "symbol": symbol,
                "name": name,
                "asset_class": asset_class,
                "unit": unit,
                "quote_currency": quote_currency,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    symbols = tuple(row[0] for row in SYSTEM_ASSETS)
    bind.execute(
        sa.text(
            "DELETE FROM asset WHERE user_id IS NULL AND symbol IN :symbols"
        ).bindparams(sa.bindparam("symbols", expanding=True)),
        {"symbols": list(symbols)},
    )
