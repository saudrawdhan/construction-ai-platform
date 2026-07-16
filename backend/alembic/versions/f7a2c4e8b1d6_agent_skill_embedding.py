"""agent skill embedding: semantic matching alongside keyword overlap

Revision ID: f7a2c4e8b1d6
Revises: c1f5a9e3d7b4
Create Date: 2026-07-13 12:00:00.000000

"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa

from alembic import op

revision: str = "f7a2c4e8b1d6"
down_revision: str | None = "c1f5a9e3d7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_skills",
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_skills_hnsw "
        "ON agent_skills USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_skills_hnsw")
    op.drop_column("agent_skills", "embedding")
