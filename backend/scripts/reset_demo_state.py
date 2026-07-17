"""Reset every AI-write and governance table back to an empty baseline, safely.

Purpose: manual testing (via the UI, the API, or the agent) writes real rows into ai_audit_logs,
ai_memories, ai_conversations, ai_messages, agent_runs, agent_skills, ai_summaries,
ai_recommendations, approval_requests, approval_history, notifications, and agent-generated
supplier_evaluations. None of that is part of the seeded operational dataset (projects, suppliers,
RFIs, ...), which this script never touches — it only clears the tables a test session itself
created.

Deletes in the correct foreign-key order (ai_messages and agent_runs before ai_conversations; child
before parent throughout) so it never fails on a constraint, unlike an ad-hoc DELETE list run in the
wrong order.

Refuses to run unless CONFIRM_RESET=1 is set, since ai_audit_logs is the governance/compliance
record — wiping it should always be a deliberate choice, never an accident. Prints row counts before
and after so you can see exactly what changed.

Run (stack must already be up):
    docker compose run --rm -e CONFIRM_RESET=1 api python -m scripts.reset_demo_state
"""

import asyncio
import os

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal, engine
from app.models import (
    AgentRun,
    AgentSkill,
    AiAuditLog,
    AiConversation,
    AiMemory,
    AiMessage,
    AiRecommendation,
    AiSummary,
    ApprovalHistory,
    ApprovalRequest,
    Notification,
    SupplierEvaluation,
)

AGENT_EVALUATIONS = SupplierEvaluation.generated_by == "agent"

# Order matters: children before parents.
TABLES: list[tuple[str, type, object | None]] = [
    ("ai_messages", AiMessage, None),
    ("agent_runs", AgentRun, None),
    ("agent_skills", AgentSkill, None),
    ("ai_audit_logs", AiAuditLog, None),
    ("ai_memories", AiMemory, None),
    ("ai_recommendations", AiRecommendation, None),
    ("ai_summaries", AiSummary, None),
    ("approval_history", ApprovalHistory, None),
    ("approval_requests", ApprovalRequest, None),
    ("notifications", Notification, None),
    ("ai_conversations", AiConversation, None),
    ("supplier_evaluations (agent-generated only)", SupplierEvaluation, AGENT_EVALUATIONS),
]


async def _count(db: AsyncSession, model: type, extra_filter: object | None) -> int:
    stmt = select(func.count()).select_from(model)
    if extra_filter is not None:
        stmt = stmt.where(extra_filter)
    return (await db.execute(stmt)).scalar_one()


async def run() -> None:
    if os.environ.get("CONFIRM_RESET") != "1":
        print("Refusing to run: set CONFIRM_RESET=1 to actually delete rows.")
        print("This clears ai_audit_logs, ai_memories, ai_conversations, agent_runs, agent_skills,")
        print("approval_requests/history, notifications, and agent-generated supplier_evaluations.")
        print("It never touches projects, suppliers, RFIs, or any other seeded operational data.")
        return

    async with AsyncSessionLocal() as db:
        before = {
            name: await _count(db, model, extra_filter) for name, model, extra_filter in TABLES
        }

        for _name, model, extra_filter in TABLES:
            stmt = delete(model)
            if extra_filter is not None:
                stmt = stmt.where(extra_filter)
            await db.execute(stmt)
        await db.commit()

        after = {
            name: await _count(db, model, extra_filter) for name, model, extra_filter in TABLES
        }

    print("Reset complete. Rows before -> after:")
    for name, _model, _extra_filter in TABLES:
        print(f"  {name}: {before[name]} -> {after[name]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
