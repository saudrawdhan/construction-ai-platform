"""full-text index on agent_runs for cross-session recall

Revision ID: b8d4f2a6c1e9
Revises: a7c3e9f1b5d2
Create Date: 2026-07-12 09:30:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "b8d4f2a6c1e9"
down_revision: str | None = "a7c3e9f1b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_runs_fts ON agent_runs USING gin "
        "(to_tsvector('simple', goal || ' ' || coalesce(final_answer, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_runs_fts")
