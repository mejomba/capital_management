"""transactions, legs, and audit log

Revision ID: 0003_transactions_audit
Revises: 0002_seed_system_assets
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_transactions_audit"
down_revision: Union[str, None] = "0002_seed_system_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NUMERIC = sa.Numeric(38, 18)

transaction_type = sa.Enum(
    "deposit", "withdrawal", "trade", "transfer", "income", "fee", "expense",
    name="transaction_type",
)
transaction_status = sa.Enum("active", "reversed", name="transaction_status")
audit_action = sa.Enum("create", "update", "reverse", "delete", name="audit_action")


def upgrade() -> None:
    op.create_table(
        "transaction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.Column("status", transaction_status, nullable=False),
        sa.Column("reversal_of", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reversal_of"], ["transaction.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transaction_user_id"), "transaction", ["user_id"])
    op.create_index(op.f("ix_transaction_occurred_at"), "transaction", ["occurred_at"])

    op.create_table(
        "transaction_leg",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", NUMERIC, nullable=False),
        sa.Column("unit_price", NUMERIC, nullable=True),
        sa.Column("price_currency", sa.String(length=16), nullable=True),
        sa.Column("fee", NUMERIC, nullable=True),
        sa.Column("fee_currency", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["transaction_id"], ["transaction.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transaction_leg_transaction_id"), "transaction_leg", ["transaction_id"]
    )
    op.create_index(
        op.f("ix_transaction_leg_account_id"), "transaction_leg", ["account_id"]
    )
    op.create_index(
        op.f("ix_transaction_leg_asset_id"), "transaction_leg", ["asset_id"]
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("diff_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"])
    op.create_index(op.f("ix_audit_log_entity_id"), "audit_log", ["entity_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_entity_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_user_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_transaction_leg_asset_id"), table_name="transaction_leg")
    op.drop_index(op.f("ix_transaction_leg_account_id"), table_name="transaction_leg")
    op.drop_index(
        op.f("ix_transaction_leg_transaction_id"), table_name="transaction_leg"
    )
    op.drop_table("transaction_leg")
    op.drop_index(op.f("ix_transaction_occurred_at"), table_name="transaction")
    op.drop_index(op.f("ix_transaction_user_id"), table_name="transaction")
    op.drop_table("transaction")
    audit_action.drop(op.get_bind(), checkfirst=True)
    transaction_status.drop(op.get_bind(), checkfirst=True)
    transaction_type.drop(op.get_bind(), checkfirst=True)
