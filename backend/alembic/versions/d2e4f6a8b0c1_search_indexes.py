"""search indexes: pgvector HNSW (cosine) + full-text GIN

Revision ID: d2e4f6a8b0c1
Revises: fc127823c853
Create Date: 2026-07-06 11:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "d2e4f6a8b0c1"
down_revision: str | None = "fc127823c853"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_embeddings_hnsw "
        "ON document_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_memories_hnsw "
        "ON ai_memories USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_embeddings_fts "
        "ON document_embeddings USING gin (to_tsvector('simple', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_embeddings_fts")
    op.execute("DROP INDEX IF EXISTS ix_ai_memories_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_document_embeddings_hnsw")
