"""Link an approval request to the record it decides

Revision ID: a3d7f1b95e02
Revises: c20c70f75acc
Create Date: 2026-07-31

An approval carried only a free-text action_type and a JSON payload, so resolving one could
record a verdict but never move the record it was about. These two columns name that record so
the decision can be applied to it.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "a3d7f1b95e02"
down_revision: str | None = "c20c70f75acc"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "approval_requests", sa.Column("subject_type", sa.String(length=50), nullable=True)
    )
    op.add_column("approval_requests", sa.Column("subject_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_approval_requests_subject_type", "approval_requests", ["subject_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_approval_requests_subject_type", table_name="approval_requests")
    op.drop_column("approval_requests", "subject_id")
    op.drop_column("approval_requests", "subject_type")
