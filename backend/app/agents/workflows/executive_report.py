"""Executive Weekly Report workflow (spec 9). Aggregates portfolio KPIs from the database
(deterministic), narrates them (LLM in real mode), and stores the result as an ai_summary so
management reports are versioned and retrievable.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows.base import localize, record_workflow_memory
from app.models import (
    AiSummary,
    Claim,
    Ncr,
    Project,
    PurchaseOrder,
    PurchaseRequest,
    Rfi,
    SafetyEvent,
)
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import ExecutiveReport, ExecutiveReportRequest
from app.services.audit import log_ai_call
from app.services.llm import LLMClient

_PENDING_PR = ("Under Review", "Pending Clarification", "Needs Rework", "Returned to Requester")


async def _count(db, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    for condition in conditions:
        stmt = stmt.where(condition)
    return int(await db.scalar(stmt) or 0)


async def run(
    db: AsyncSession, *, payload: ExecutiveReportRequest, llm: LLMClient, language: str = "en"
) -> ExecutiveReport:
    project_id = payload.project_id
    today = date.today()
    scope = f"Project {project_id}" if project_id else "All projects"

    def scoped(model, column_name: str = "project_id"):
        return (getattr(model, column_name) == project_id,) if project_id else ()

    projects_total = await _count(db, Project, *((Project.id == project_id,) if project_id else ()))
    delayed = await _count(
        db, Project,
        Project.status.in_(["Delayed", "On Hold"]),
        *((Project.id == project_id,) if project_id else ()),
    )
    overdue_rfis = await _count(
        db, Rfi, Rfi.status != "Closed", Rfi.required_date < today, *scoped(Rfi)
    )
    late_pos = await _count(
        db, PurchaseOrder, PurchaseOrder.is_late.is_(True), *scoped(PurchaseOrder)
    )
    open_ncrs = await _count(db, Ncr, Ncr.status != "Closed", *scoped(Ncr))
    recent_cutoff = today - timedelta(days=90)
    safety = await _count(
        db, SafetyEvent, SafetyEvent.event_date >= recent_cutoff, *scoped(SafetyEvent)
    )
    pending_prs = await _count(
        db, PurchaseRequest, PurchaseRequest.status.in_(_PENDING_PR), *scoped(PurchaseRequest)
    )
    open_claims = await _count(db, Claim, Claim.status != "Closed", *scoped(Claim))

    highlights = [
        f"{delayed} project(s) delayed or on hold",
        f"{overdue_rfis} overdue RFI(s) blocking execution",
        f"{late_pos} late purchase order(s)",
        f"{open_ncrs} open non-conformance report(s)",
        f"{safety} safety event(s) in the last 90 days",
        f"{pending_prs} purchase request(s) awaiting action",
        f"{open_claims} open claim(s)",
    ]

    narrative = (
        f"Weekly executive summary for {scope.lower()}: {delayed} project(s) need attention, "
        f"{overdue_rfis} RFIs are overdue, and {late_pos} purchase orders were delivered late. "
        f"There are {open_ncrs} open NCRs and {pending_prs} purchase requests awaiting action. "
        "Prioritize overdue RFIs and procurement blockers to protect the programme."
    )

    if llm.provider != "mock":
        result = await llm.complete(
            system=localize(
                "You write concise executive construction status reports for senior management.",
                language,
            ),
            messages=[{"role": "user", "content": "KPIs:\n" + "\n".join(highlights)}],
            max_tokens=700,
        )
        narrative = result.text.strip() or narrative

    summary_id: int | None = None
    if payload.store:
        summary = AiSummary(
            project_id=project_id,
            summary_type="executive_weekly",
            period_start=recent_cutoff,
            period_end=today,
            content=narrative,
            structured_output={"highlights": highlights},
        )
        db.add(summary)
        await db.flush()
        summary_id = summary.id

        # The KPI figures themselves are recomputable from the database at any moment, so they
        # are not knowledge; the management reading of them is. Only the narrative is kept, and
        # it always supersedes the previous one for this scope — the weekly scheduled run calls
        # this with store=True, so appending instead would add a near-identical row every week
        # and steadily crowd genuine lessons out of retrieval.
        await record_workflow_memory(
            db,
            data=MemoryCreate(
                project_id=project_id,
                category=MemoryCategory.ISSUE,
                summary=f"Executive position for {scope.lower()} as at {today}: " + "; ".join(
                    highlights[:3]
                ),
                detail=narrative,
                source_type="executive_report",
                source_id=project_id,
                confidence=0.6,
            ),
            supersede=True,
        )

    await log_ai_call(
        db,
        workflow="executive_weekly_report",
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
        source_ids={"project": project_id},
        output_excerpt=narrative,
    )

    return ExecutiveReport(
        scope=scope,
        projects_total=projects_total,
        delayed_or_onhold=delayed,
        overdue_rfis=overdue_rfis,
        late_purchase_orders=late_pos,
        open_ncrs=open_ncrs,
        recent_safety_events=safety,
        pending_purchase_requests=pending_prs,
        highlights=highlights,
        narrative=narrative,
        summary_id=summary_id,
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
    )
