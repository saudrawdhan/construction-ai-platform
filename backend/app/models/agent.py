from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.database.base import Base
from app.models.mixins import TimestampMixin

_EMBED_DIM = get_settings().embedding_dimensions


class AgentSkill(Base, TimestampMixin):
    """A reusable procedure the agent authored from experience: a named, parameterized
    sequence of tool calls (stored as data, not executable code) plus usage statistics so
    it can be reused and refined over time."""

    __tablename__ = "agent_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    trigger_keywords: Mapped[list] = mapped_column(JSONB, default=list)
    plan: Mapped[list] = mapped_column(JSONB, default=list)
    parameters: Mapped[list] = mapped_column(JSONB, default=list)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(50), default="agent")
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Embedding of the skill's generic description — lets a later goal match on MEANING
    # ("how risky is supplier 12" ~ "assess the risk of supplier 3"), not only shared
    # keywords. A live audit test proved keyword-only matching fragments into a separate
    # skill per phrasing of the same intent; this is the semantic half of a hybrid match.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM))


class AgentRun(Base, TimestampMixin):
    """One execution of the agent loop against a goal: the full trajectory of reasoning
    steps and tool calls, the grounded final answer, and links to any skill reused or
    created. The trajectory is the auditable record of how the agent reached its answer."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    # Groups turns of the same back-and-forth together (shared with the copilot's
    # ai_conversations table) so a follow-up goal can resolve "it"/"this project"/"the
    # suppliers involved" against what was actually just discussed, not re-plan from nothing.
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_conversations.id"), index=True
    )
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    final_answer: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    skill_used_id: Mapped[int | None] = mapped_column(ForeignKey("agent_skills.id"), index=True)
    skill_created_id: Mapped[int | None] = mapped_column(ForeignKey("agent_skills.id"))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
