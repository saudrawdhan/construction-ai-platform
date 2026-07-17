"""document file storage

Revision ID: c20c70f75acc
Revises: f7a2c4e8b1d6
Create Date: 2026-07-17 03:40:59.248561

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c20c70f75acc'
down_revision: str | None = 'f7a2c4e8b1d6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('storage_path', sa.String(length=255), nullable=True))
    op.add_column('documents', sa.Column('original_filename', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'original_filename')
    op.drop_column('documents', 'storage_path')
