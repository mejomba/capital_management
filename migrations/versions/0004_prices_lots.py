"""prices, lots, and lot consumptions

Revision ID: 0004_prices_lots
Revises: 0003_transactions_audit
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_prices_lots"
down_revision: Union[str, None] = "0003_transactions_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NUMERIC = sa.Numeric(38, 18)


def upgrade() -> None:
    op.create_table(
        "price",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("price", NUMERIC, nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_user_id"), "price", ["user_id"])
    op.create_index(op.f("ix_price_asset_id"), "price", ["asset_id"])
    op.create_index(op.f("ix_price_as_of"), "price", ["as_of"])

    op.create_table(
        "lot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_leg_id", sa.Uuid(), nullable=False),
        sa.Column("original_qty", NUMERIC, nullable=False),
        sa.Column("remaining_qty", NUMERIC, nullable=False),
        sa.Column("unit_cost", NUMERIC, nullable=True),
        sa.Column("cost_currency", sa.String(length=16), nullable=True),
        sa.Column("unit_cost_irr", NUMERIC, nullable=True),
        sa.Column("unit_cost_usd", NUMERIC, nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["source_leg_id"], ["transaction_leg.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lot_user_id"), "lot", ["user_id"])
    op.create_index(op.f("ix_lot_account_id"), "lot", ["account_id"])
    op.create_index(op.f("ix_lot_asset_id"), "lot", ["asset_id"])
    op.create_index(op.f("ix_lot_acquired_at"), "lot", ["acquired_at"])

    op.create_table(
        "lot_consumption",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("sell_leg_id", sa.Uuid(), nullable=False),
        sa.Column("qty_consumed", NUMERIC, nullable=False),
        sa.Column("proceeds_unit_price", NUMERIC, nullable=True),
        sa.Column("proceeds_currency", sa.String(length=16), nullable=True),
        sa.Column("realized_pnl_irr", NUMERIC, nullable=True),
        sa.Column("realized_pnl_usd", NUMERIC, nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lot_id"], ["lot.id"]),
        sa.ForeignKeyConstraint(["sell_leg_id"], ["transaction_leg.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lot_consumption_lot_id"), "lot_consumption", ["lot_id"])
    op.create_index(
        op.f("ix_lot_consumption_consumed_at"), "lot_consumption", ["consumed_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lot_consumption_consumed_at"), table_name="lot_consumption")
    op.drop_index(op.f("ix_lot_consumption_lot_id"), table_name="lot_consumption")
    op.drop_table("lot_consumption")
    op.drop_index(op.f("ix_lot_acquired_at"), table_name="lot")
    op.drop_index(op.f("ix_lot_asset_id"), table_name="lot")
    op.drop_index(op.f("ix_lot_account_id"), table_name="lot")
    op.drop_index(op.f("ix_lot_user_id"), table_name="lot")
    op.drop_table("lot")
    op.drop_index(op.f("ix_price_as_of"), table_name="price")
    op.drop_index(op.f("ix_price_asset_id"), table_name="price")
    op.drop_index(op.f("ix_price_user_id"), table_name="price")
    op.drop_table("price")
