"""memory full-text index for hybrid memory search

Revision ID: e4a1b9c7d2f3
Revises: d2e4f6a8b0c1
Create Date: 2026-07-06 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "e4a1b9c7d2f3"
down_revision: str | None = "d2e4f6a8b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_memories_fts "
        "ON ai_memories USING gin (to_tsvector('simple', summary))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_memories_fts")
