"""init orders

Revision ID: 20260211_0002
Revises: 20260211_0001
Create Date: 2026-02-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260211_0002"
down_revision = "20260211_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
