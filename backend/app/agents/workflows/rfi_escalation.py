"""RFI Escalation workflow (spec 9). Detects overdue RFIs for a project, summarizes the
blockers with a suggested action per item, and drafts an escalation message (LLM in real
mode, template in mock). The draft is advisory — sending is gated by human approval later.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows.base import (
    gather_memory_context,
    localize,
    record_workflow_memory,
)
from app.models import Rfi
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import RfiEscalation, RfiEscalationItem
from app.services.audit import log_ai_call
from app.services.llm import LLMClient


def _suggested_action(priority: str, days_overdue: int) -> str:
    if priority == "High" or days_overdue > 30:
        return "Escalate to the consultant lead today; blocking site progress."
    if priority == "Medium":
        return "Send a reminder and request a response within 3 days."
    return "Follow up in the next coordination meeting."


async def run(
    db: AsyncSession, *, project_id: int, llm: LLMClient, language: str = "en"
) -> RfiEscalation:
    today = date.today()
    rows = await db.scalars(
        select(Rfi)
        .where(Rfi.project_id == project_id, Rfi.status != "Closed", Rfi.required_date < today)
        .order_by(Rfi.required_date)
    )
    items = [
        RfiEscalationItem(
            rfi_number=rfi.rfi_number,
            subject=rfi.subject,
            discipline=rfi.discipline,
            days_overdue=(today - rfi.required_date).days,
            assigned_to=rfi.assigned_to,
            priority=rfi.priority,
            suggested_action=_suggested_action(rfi.priority, (today - rfi.required_date).days),
        )
        for rfi in rows
    ]

    memory_context, memory_ids = await gather_memory_context(
        db,
        query=f"overdue RFI escalation blockers project {project_id}",
        project_id=project_id,
        k=3,
    )

    if not items:
        message = "No overdue RFIs for this project. No escalation required."
    else:
        worst = items[0]
        message = (
            f"Escalation: {len(items)} RFI(s) are overdue on this project. "
            f"The most critical is {worst.rfi_number} ({worst.subject}), {worst.days_overdue} "
            f"days overdue and assigned to {worst.assigned_to}. Please provide responses to "
            "avoid further impact on the site programme."
        )
        if llm.provider != "mock":
            listing = "\n".join(
                f"- {i.rfi_number} ({i.discipline}) {i.days_overdue}d overdue, "
                f"assigned to {i.assigned_to}, priority {i.priority}"
                for i in items[:10]
            )
            context = (
                f"Overdue RFIs for project {project_id}:\n{listing}\n"
                f"Related memories:\n{memory_context}\n"
                "Draft a short, firm, professional escalation email to the consultant."
            )
            result = await llm.complete(
                system=localize(
                    "You draft concise construction escalation correspondence.", language
                ),
                messages=[{"role": "user", "content": context}],
                max_tokens=600,
            )
            message = result.text.strip() or message

    # "No overdue RFIs" is the healthy state and carries no lesson, so only a real backlog is
    # recorded. The backlog is a moving position rather than a fixed fact about a record, so a
    # re-run supersedes the previous entry instead of stacking another one beside it.
    if items:
        worst = items[0]
        await record_workflow_memory(
            db,
            data=MemoryCreate(
                project_id=project_id,
                category=MemoryCategory.ISSUE,
                summary=(
                    f"{len(items)} overdue RFI(s) blocking project {project_id}; longest is "
                    f"{worst.rfi_number} at {worst.days_overdue} days ({worst.discipline})."
                ),
                detail="\n".join(
                    f"{i.rfi_number} ({i.discipline}), {i.days_overdue}d overdue, "
                    f"assigned to {i.assigned_to}, priority {i.priority}"
                    for i in items[:10]
                ),
                source_type="rfi_escalation",
                source_id=project_id,
                confidence=0.7,
            ),
            supersede=True,
        )

    await log_ai_call(
        db,
        workflow="rfi_escalation",
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
        source_ids={"project": project_id, "overdue_rfis": len(items), "memory": memory_ids},
        output_excerpt=message,
    )

    return RfiEscalation(
        project_id=project_id,
        overdue_count=len(items),
        items=items,
        escalation_message=message,
        memory_used=memory_ids,
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
    )
