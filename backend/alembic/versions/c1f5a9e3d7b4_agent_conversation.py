"""agent run conversation grouping

Revision ID: c1f5a9e3d7b4
Revises: b8d4f2a6c1e9
Create Date: 2026-07-13 08:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1f5a9e3d7b4"
down_revision: str | None = "b8d4f2a6c1e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs", sa.Column("conversation_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_agent_runs_conversation_id", "agent_runs", "ai_conversations",
        ["conversation_id"], ["id"],
    )
    op.create_index(
        "ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_agent_runs_conversation_id", table_name="agent_runs")
    op.drop_constraint("fk_agent_runs_conversation_id", "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "conversation_id")
