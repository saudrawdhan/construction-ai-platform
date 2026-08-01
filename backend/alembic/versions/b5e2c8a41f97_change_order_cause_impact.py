"""Link a change order to its cause and record its schedule impact

Revision ID: b5e2c8a41f97
Revises: a3d7f1b95e02
Create Date: 2026-07-31

A change order recorded that something changed and what it cost, but not what triggered it or
what it did to the programme — leaving no way to answer the two questions a commercial claim
ultimately rests on.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "b5e2c8a41f97"
down_revision: str | None = "a3d7f1b95e02"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("change_orders", sa.Column("cause_rfi_id", sa.Integer(), nullable=True))
    op.add_column("change_orders", sa.Column("cause_category", sa.String(length=50), nullable=True))
    op.add_column("change_orders", sa.Column("cause_description", sa.Text(), nullable=True))
    op.add_column("change_orders", sa.Column("schedule_impact_days", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_change_orders_cause_rfi_id", "change_orders", "rfis", ["cause_rfi_id"], ["id"]
    )
    op.create_index("ix_change_orders_cause_rfi_id", "change_orders", ["cause_rfi_id"])
    op.create_index("ix_change_orders_cause_category", "change_orders", ["cause_category"])


def downgrade() -> None:
    op.drop_index("ix_change_orders_cause_category", table_name="change_orders")
    op.drop_index("ix_change_orders_cause_rfi_id", table_name="change_orders")
    op.drop_constraint("fk_change_orders_cause_rfi_id", "change_orders", type_="foreignkey")
    op.drop_column("change_orders", "schedule_impact_days")
    op.drop_column("change_orders", "cause_description")
    op.drop_column("change_orders", "cause_category")
    op.drop_column("change_orders", "cause_rfi_id")
