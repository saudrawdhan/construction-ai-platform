"""agent core: agent_skills and agent_runs

Revision ID: a7c3e9f1b5d2
Revises: e4a1b9c7d2f3
Create Date: 2026-07-12 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7c3e9f1b5d2"
down_revision: str | None = "e4a1b9c7d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("trigger_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_skills_name", "agent_skills", ["name"], unique=True)
    op.create_index("ix_agent_skills_status", "agent_skills", ["status"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("skill_used_id", sa.Integer(), nullable=True),
        sa.Column("skill_created_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["skill_used_id"], ["agent_skills.id"]),
        sa.ForeignKeyConstraint(["skill_created_id"], ["agent_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"], unique=False)
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)
    op.create_index(
        "ix_agent_runs_skill_used_id", "agent_runs", ["skill_used_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("agent_skills")
