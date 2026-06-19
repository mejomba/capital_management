"""initial schema: user, account, asset

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


account_type = sa.Enum(
    "bank",
    "exchange",
    "brokerage",
    "wallet",
    "physical",
    "property",
    "other",
    name="account_type",
)

asset_class = sa.Enum(
    "equity",
    "fund",
    "crypto",
    "metal",
    "forex",
    "real_estate",
    "fiat",
    "other",
    name="asset_class",
)


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", account_type, nullable=False),
        sa.Column("currency_hint", sa.String(length=16), nullable=True),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_account_user_id"), "account", ["user_id"], unique=False)

    op.create_table(
        "asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_class", asset_class, nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_user_id"), "asset", ["user_id"], unique=False)
    op.create_index(op.f("ix_asset_symbol"), "asset", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_asset_symbol"), table_name="asset")
    op.drop_index(op.f("ix_asset_user_id"), table_name="asset")
    op.drop_table("asset")
    op.drop_index(op.f("ix_account_user_id"), table_name="account")
    op.drop_table("account")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
    asset_class.drop(op.get_bind(), checkfirst=True)
    account_type.drop(op.get_bind(), checkfirst=True)
