"""Tool registry for the construction agent.

Each tool wraps an existing platform capability (memory/document retrieval, the six AI
workflows, entity lookups) behind a uniform interface so the agent loop can select and call
them by name. A tool returns a text ``summary`` (what the agent reads as an observation),
structured ``data``, and ``sources`` for grounding/attribution. Adding a capability to the
agent is a matter of registering another Tool — the loop itself never changes.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.content_shield import (
    looks_like_injection as _looks_like_injection,  # noqa: F401  (re-exported for tests)
)
from app.agents.content_shield import (
    shield as _shield,
)
from app.agents.workflows import (
    executive_report,
    meeting_summary,
    pr_review,
    rfi_escalation,
    site_report,
    supplier_risk,
)
from app.models import (
    ChangeOrder,
    Claim,
    MeetingActionItem,
    Project,
    ProjectRisk,
    SafetyEvent,
)
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import (
    ExecutiveReportRequest,
    MeetingSummarizeRequest,
    SiteReportAnalyzeRequest,
)
from app.security.roles import Role
from app.services.embeddings import EmbeddingClient
from app.services.llm import LLMClient
from app.services.memory import create_memory, search_memories
from app.services.retrieval import hybrid_search

_STOPWORDS = frozenset(
    "the a an is are was were be of to in on at by for with and or not do did why what how "
    "when where which who that this these those it its we our you your i me my will would can "
    "could should has have had any some all more most about into over then than as show tell "
    "list please previously earlier before last time past recall remember note record".split()
)


def keyword_tsquery(query: str) -> str:
    """Reduce free text to an OR-combined ``to_tsquery`` of substantive keywords. Stop words and
    short tokens are dropped so natural-language phrasing does not suppress every match; Arabic
    tokens are preserved. Returns an empty string when nothing substantive remains.

    ``\\w`` is Unicode-aware and already matches Arabic letters while correctly excluding Arabic
    punctuation. An explicit U+0600-U+06FF range was previously added alongside it, which also swept
    in ؟ ، ؛ ٪ and corrupted the token they attached to. Do not re-add it."""
    tokens = re.findall(r"\w+", query.lower())
    terms = [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]
    return " | ".join(dict.fromkeys(terms))


# The content shield (_shield / _looks_like_injection) lives in app.agents.content_shield so the
# copilot's grounded RAG applies the exact same defence as these tools — one implementation, no
# drift between the two surfaces that feed retrieved content into an LLM.


def _age_desc(created_at: datetime | None) -> str:
    """A coarse, human-readable age so a stale or a fresh memory reads differently to the
    planner — retrieval ranking has no recency signal, so this is surfaced as text instead."""
    if created_at is None:
        return "age unknown"
    now = datetime.now(UTC)
    stamp = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    days = max((now - stamp).days, 0)
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        return f"{days // 30} month(s) ago"
    return f"{days // 365} year(s) ago"


@dataclass
class ToolContext:
    db: AsyncSession
    llm: LLMClient
    embedder: EmbeddingClient
    user_id: int | None = None
    user_role: str | None = None


@dataclass
class ToolResult:
    summary: str
    data: dict = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)


@dataclass
class ToolParam:
    name: str
    type: str
    required: bool
    description: str


@dataclass
class Tool:
    name: str
    description: str
    params: list[ToolParam]
    handler: Callable[..., Awaitable[ToolResult]]
    # Roles allowed to invoke this tool, matching the role gate on the equivalent direct API
    # endpoint. None means open to any role that can reach the agent at all (read-only/general
    # capabilities). The agent must never let a user do through a goal what they could not do
    # by calling the underlying endpoint themselves.
    allowed_roles: frozenset[str] | None = None

    async def run(self, ctx: ToolContext, **args) -> ToolResult:
        return await self.handler(ctx, **args)

    def allowed_for(self, role: str | None) -> bool:
        return self.allowed_roles is None or role in self.allowed_roles

    def unauthorized_message(self, role: str | None) -> str:
        allowed = ", ".join(sorted(self.allowed_roles or []))
        return (
            f"Not authorized: the role '{role or 'unknown'}' cannot use '{self.name}'. "
            f"This action is restricted to: {allowed}."
        )

    def signature(self) -> str:
        parts = [
            f"{p.name}:{p.type}{'' if p.required else '?'}" for p in self.params
        ]
        return f"{self.name}({', '.join(parts)}) — {self.description}"


async def _search_memory(ctx: ToolContext, query: str, project_id: int | None = None) -> ToolResult:
    results = await search_memories(
        ctx.db, ctx.embedder, query=query, k=4, project_id=project_id
    )
    if not results:
        return ToolResult(summary="No related operational memories on record.")
    # Confidence and age are stored but were never surfaced to the planner, so two
    # contradictory memories looked equally authoritative regardless of how sure the
    # original source was or how long ago it was recorded — this makes both visible so a
    # low-confidence or stale finding can be weighed accordingly, not treated as equal fact.
    def _label(memory) -> str:
        confidence = memory.confidence if memory.confidence is not None else "n/a"
        return f"- [{memory.category}, confidence {confidence}, {_age_desc(memory.created_at)}]"

    lines = [_shield(_label(memory), memory.summary) for memory, _ in results]
    sources = [
        {"type": "memory", "id": memory.id, "label": memory.summary[:80]}
        for memory, _ in results
    ]
    return ToolResult(summary="\n".join(lines), data={"count": len(results)}, sources=sources)


async def _search_documents(
    ctx: ToolContext, query: str, project_id: int | None = None
) -> ToolResult:
    hits = await hybrid_search(ctx.db, ctx.embedder, query=query, k=4, project_id=project_id)
    if not hits:
        return ToolResult(summary="No documents match this query.")
    lines = [
        _shield(
            f"- [{hit.source_type} #{hit.source_id}]", hit.content, display=hit.content[:200]
        )
        for hit in hits
    ]
    sources = [
        {"type": hit.source_type, "id": hit.source_id, "label": hit.content[:80]}
        for hit in hits
    ]
    return ToolResult(summary="\n".join(lines), data={"count": len(hits)}, sources=sources)


async def _supplier_risk(ctx: ToolContext, supplier_id: int) -> ToolResult:
    assessment = await supplier_risk.run(ctx.db, supplier_id=supplier_id, llm=ctx.llm)
    if assessment is None:
        return ToolResult(summary=f"No supplier found with id {supplier_id}.")
    summary = (
        f"Supplier {assessment.supplier_name}: {assessment.risk_level} risk "
        f"(score {assessment.risk_score}), on-time {assessment.on_time_rate}%, "
        f"{assessment.ncr_count} NCR(s). {assessment.recommendation}"
    )
    sources = [
        {"type": "memory", "id": mid, "label": "supplier memory"}
        for mid in assessment.memory_used
    ]
    return ToolResult(summary=summary, data=assessment.model_dump(mode="json"), sources=sources)


async def _purchase_request_review(ctx: ToolContext, pr_id: int) -> ToolResult:
    review = await pr_review.run(ctx.db, pr_id=pr_id, llm=ctx.llm)
    if review is None:
        return ToolResult(summary=f"No purchase request found with id {pr_id}.")
    missing = ", ".join(review.missing_information) or "none"
    summary = (
        f"PR {review.request_no}: {review.risk_level} risk. Missing: {missing}. "
        f"{review.recommendation}"
    )
    return ToolResult(summary=summary, data=review.model_dump(mode="json"))


async def _rfi_escalation(ctx: ToolContext, project_id: int) -> ToolResult:
    result = await rfi_escalation.run(ctx.db, project_id=project_id, llm=ctx.llm)
    summary = (
        f"Project {project_id}: {result.overdue_count} overdue RFI(s). "
        f"{result.escalation_message}"
    )
    return ToolResult(summary=summary, data=result.model_dump(mode="json"))


async def _executive_report(ctx: ToolContext, project_id: int | None = None) -> ToolResult:
    report = await executive_report.run(
        ctx.db,
        payload=ExecutiveReportRequest(project_id=project_id, store=False),
        llm=ctx.llm,
    )
    summary = (
        f"{report.scope}: {report.projects_total} projects, {report.delayed_or_onhold} "
        f"delayed/on-hold, {report.overdue_rfis} overdue RFIs, {report.late_purchase_orders} "
        f"late POs, {report.open_ncrs} open NCRs, {report.pending_purchase_requests} pending "
        f"PRs. {report.narrative}"
    )
    return ToolResult(summary=summary, data=report.model_dump(mode="json"))


async def _meeting_summarize(ctx: ToolContext, project_id: int, notes: str) -> ToolResult:
    result = await meeting_summary.run(
        ctx.db, project_id=project_id,
        payload=MeetingSummarizeRequest(notes=notes, store=False), llm=ctx.llm,
    )
    summary = (
        f"Project {project_id} meeting: {result.summary} "
        f"({len(result.action_items)} action item(s), {len(result.decisions)} decision(s))."
    )
    return ToolResult(summary=summary, data=result.model_dump(mode="json"))


async def _analyze_site_report(ctx: ToolContext, project_id: int, text: str) -> ToolResult:
    result = await site_report.run(
        ctx.db, project_id=project_id,
        payload=SiteReportAnalyzeRequest(text=text, store=False), llm=ctx.llm,
    )
    summary = (
        f"Project {project_id} site report: {result.summary} "
        f"Recommended escalation: {result.recommended_escalation}"
    )
    return ToolResult(summary=summary, data=result.model_dump(mode="json"))


async def _get_project(ctx: ToolContext, project_id: int) -> ToolResult:
    project = await ctx.db.get(Project, project_id)
    if project is None:
        return ToolResult(summary=f"No project found with id {project_id}.")
    summary = (
        f"Project {project.project_code} — {project.project_name} ({project.city}), "
        f"status {project.status}, client {project.client_name}, budget SAR {project.budget}."
    )
    data = {
        "id": project.id,
        "project_code": project.project_code,
        "project_name": project.project_name,
        "city": project.city,
        "status": project.status,
        "budget": str(project.budget),
    }
    return ToolResult(summary=summary, data=data, sources=[{"type": "project", "id": project.id}])


async def _remember(
    ctx: ToolContext,
    summary: str,
    category: str = "lesson_learned",
    detail: str | None = None,
    project_id: int | None = None,
) -> ToolResult:
    try:
        cat = MemoryCategory(category)
    except ValueError:
        cat = MemoryCategory.LESSON_LEARNED
    memory = await create_memory(
        ctx.db,
        ctx.embedder,
        MemoryCreate(
            category=cat, summary=summary, detail=detail, project_id=project_id,
            source_type="agent_run", confidence=0.7,
        ),
        created_by="agent",
    )
    return ToolResult(
        summary=f"Stored a {cat.value} memory: {summary[:120]}",
        data={"memory_id": memory.id},
        sources=[{"type": "memory", "id": memory.id, "label": summary[:80]}],
    )


async def _recall_past_sessions(ctx: ToolContext, query: str) -> ToolResult:
    tsquery = keyword_tsquery(query)
    if not tsquery:
        return ToolResult(summary="No searchable terms to recall past sessions.")
    # Prioritize the current user's own past runs (their own recent work) but still fall back
    # to the wider organizational record — the agent remembers what the company knows, and
    # additionally recalls this person's own history first, without needing a personal profile.
    sql = text(
        "SELECT id, goal, final_answer, user_id FROM agent_runs "
        "WHERE final_answer IS NOT NULL AND to_tsvector('simple', "
        "goal || ' ' || coalesce(final_answer, '')) @@ to_tsquery('simple', :q) "
        "ORDER BY (user_id IS NOT DISTINCT FROM :uid) DESC, created_at DESC LIMIT 4"
    )
    rows = list(await ctx.db.execute(sql, {"q": tsquery, "uid": ctx.user_id}))
    if not rows:
        return ToolResult(summary="No prior agent sessions match this topic.")
    lines = [
        _shield(
            f"- (run #{rid}, {'you' if uid == ctx.user_id else 'a colleague'})",
            f"goal: {goal} -> {ans or ''}",
            display=f"goal: {goal} -> {(ans or '')[:160]}",
        )
        for rid, goal, ans, uid in rows
    ]
    sources = [{"type": "agent_run", "id": rid, "label": goal[:80]} for rid, goal, _, _ in rows]
    return ToolResult(summary="\n".join(lines), data={"count": len(rows)}, sources=sources)


async def _get_claims(ctx: ToolContext, project_id: int) -> ToolResult:
    rows = list(
        await ctx.db.scalars(
            select(Claim).where(Claim.project_id == project_id).order_by(Claim.id)
        )
    )
    if not rows:
        return ToolResult(summary=f"No claims on record for project {project_id}.")
    total = sum(float(c.amount) for c in rows)
    by_status: dict[str, int] = {}
    for c in rows:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    status_line = ", ".join(f"{count} {status}" for status, count in by_status.items())
    lines = [
        f"- {c.claim_number} ({c.claim_type}): SAR {float(c.amount):,.0f}, status {c.status}"
        for c in rows
    ]
    summary = (
        f"Project {project_id} has {len(rows)} claim(s) totaling SAR {total:,.0f} "
        f"({status_line}).\n" + "\n".join(lines)
    )
    return ToolResult(
        summary=summary,
        data={"count": len(rows), "total_amount": total},
        sources=[{"type": "claim", "id": c.id, "label": c.claim_number} for c in rows],
    )


async def _get_change_orders(ctx: ToolContext, project_id: int) -> ToolResult:
    rows = list(
        await ctx.db.scalars(
            select(ChangeOrder).where(ChangeOrder.project_id == project_id).order_by(ChangeOrder.id)
        )
    )
    if not rows:
        return ToolResult(summary=f"No change orders on record for project {project_id}.")
    total = sum(float(c.value) for c in rows)
    by_status: dict[str, int] = {}
    for c in rows:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    status_line = ", ".join(f"{count} {status}" for status, count in by_status.items())
    lines = [
        f"- {c.co_number}: SAR {float(c.value):,.0f}, status {c.status}" for c in rows
    ]
    summary = (
        f"Project {project_id} has {len(rows)} change order(s) totaling SAR {total:,.0f} "
        f"({status_line}).\n" + "\n".join(lines)
    )
    return ToolResult(
        summary=summary,
        data={"count": len(rows), "total_value": total},
        sources=[{"type": "change_order", "id": c.id, "label": c.co_number} for c in rows],
    )


async def _get_safety_events(ctx: ToolContext, project_id: int) -> ToolResult:
    # Live testing found a real, safety-relevant gap: with no tool covering this table at all,
    # a direct question about safety incidents got a confident "no recent incidents" answer
    # while a real High-severity event sat on record the whole time. Unlike claims and change
    # orders, this table has no REST endpoint of its own to match a role gate against — every
    # other read-only operational lookup in this registry is open to any agent-eligible role,
    # so this follows that same established default rather than inventing a stricter one.
    rows = list(
        await ctx.db.scalars(
            select(SafetyEvent)
            .where(SafetyEvent.project_id == project_id)
            .order_by(SafetyEvent.event_date.desc())
        )
    )
    if not rows:
        return ToolResult(summary=f"No safety events on record for project {project_id}.")
    by_severity: dict[str, int] = {}
    for e in rows:
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
    severity_line = ", ".join(f"{count} {sev}" for sev, count in by_severity.items())
    lines = [
        f"- {e.event_date}: {e.severity} — {e.description} "
        f"(corrective action: {e.corrective_action})"
        for e in rows[:10]
    ]
    summary = (
        f"Project {project_id} has {len(rows)} safety event(s) on record ({severity_line}).\n"
        + "\n".join(lines)
    )
    return ToolResult(
        summary=summary,
        data={"count": len(rows)},
        sources=[{"type": "safety_event", "id": e.id, "label": e.severity} for e in rows],
    )


# Both registers store status as free text with an "Open" default rather than an enum, so a
# closed record is recognized by value rather than assumed — anything outside this set counts as
# still open, which fails safe: an unfamiliar status is surfaced for attention, never hidden.
_CLOSED_STATUSES = frozenset(
    {"closed", "done", "completed", "resolved", "cancelled", "canceled"}
)

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _severity_rank(severity: str | None) -> int:
    return _SEVERITY_ORDER.get((severity or "").lower(), len(_SEVERITY_ORDER))


async def _get_project_risks(ctx: ToolContext, project_id: int) -> ToolResult:
    rows = list(
        await ctx.db.scalars(select(ProjectRisk).where(ProjectRisk.project_id == project_id))
    )
    if not rows:
        return ToolResult(summary=f"No risks on record for project {project_id}.")
    open_rows = [r for r in rows if (r.status or "").lower() not in _CLOSED_STATUSES]
    sources = [{"type": "project_risk", "id": r.id, "label": r.title[:80]} for r in rows]
    if not open_rows:
        return ToolResult(
            summary=f"Project {project_id} has {len(rows)} risk(s) on record, all closed.",
            data={"count": len(rows), "open_count": 0},
            sources=sources,
        )
    ranked = sorted(open_rows, key=lambda r: (_severity_rank(r.severity), r.id))
    by_severity: dict[str, int] = {}
    for risk in ranked:
        by_severity[risk.severity] = by_severity.get(risk.severity, 0) + 1
    severity_line = ", ".join(f"{count} {sev}" for sev, count in by_severity.items())
    # Title and description are free text a user types into the risk register, so they reach the
    # planner through the same shield every other retrieved content path uses.
    lines = [
        _shield(
            f"- [{risk.severity} severity, likelihood {risk.likelihood or 'unspecified'}, "
            f"status {risk.status}, owner {risk.owner or 'unassigned'}]",
            f"{risk.title}. {risk.description}" if risk.description else risk.title,
        )
        for risk in ranked[:10]
    ]
    summary = (
        f"Project {project_id} has {len(rows)} risk(s) on record, {len(open_rows)} still open "
        f"({severity_line}).\n" + "\n".join(lines)
    )
    return ToolResult(
        summary=summary,
        data={"count": len(rows), "open_count": len(open_rows)},
        sources=sources,
    )


async def _get_open_action_items(ctx: ToolContext, project_id: int) -> ToolResult:
    rows = list(
        await ctx.db.scalars(
            select(MeetingActionItem)
            .where(MeetingActionItem.project_id == project_id)
            .order_by(
                MeetingActionItem.due_date.is_(None),
                MeetingActionItem.due_date,
                MeetingActionItem.id,
            )
        )
    )
    if not rows:
        return ToolResult(summary=f"No meeting action items on record for project {project_id}.")
    open_rows = [i for i in rows if (i.status or "").lower() not in _CLOSED_STATUSES]
    sources = [
        {"type": "meeting_action_item", "id": i.id, "label": i.description[:80]} for i in rows
    ]
    if not open_rows:
        return ToolResult(
            summary=(
                f"Project {project_id} has {len(rows)} action item(s) on record, none still open."
            ),
            data={"count": len(rows), "open_count": 0, "overdue_count": 0},
            sources=sources,
        )
    today = datetime.now(UTC).date()

    def _is_overdue(item: MeetingActionItem) -> bool:
        return item.due_date is not None and item.due_date < today

    overdue = [i for i in open_rows if _is_overdue(i)]
    # An action item's description is written by the meeting-summary workflow from raw notes,
    # which may originate in an uploaded document — so it is untrusted text on the same footing
    # as anything else retrieved, and is shielded accordingly.
    lines = [
        _shield(
            f"- [owner {item.owner or 'unassigned'}, "
            f"due {item.due_date or 'no date'}{', OVERDUE' if _is_overdue(item) else ''}, "
            f"status {item.status}]",
            item.description,
        )
        for item in open_rows[:10]
    ]
    summary = (
        f"Project {project_id} has {len(open_rows)} open action item(s) of {len(rows)} on "
        f"record, {len(overdue)} overdue.\n" + "\n".join(lines)
    )
    return ToolResult(
        summary=summary,
        data={
            "count": len(rows),
            "open_count": len(open_rows),
            "overdue_count": len(overdue),
        },
        sources=sources,
    )


async def _find_project(ctx: ToolContext, query: str) -> ToolResult:
    like = f"%{query}%"
    stmt = (
        select(Project)
        .where(Project.project_name.ilike(like) | Project.project_code.ilike(like))
        .limit(5)
    )
    rows = list(await ctx.db.scalars(stmt))
    if not rows:
        return ToolResult(summary=f"No project matches '{query}'.")
    lines = [f"- #{p.id} {p.project_code}: {p.project_name} ({p.status})" for p in rows]
    return ToolResult(summary="\n".join(lines), data={"ids": [p.id for p in rows]})


def build_tool_registry() -> dict[str, Tool]:
    tools = [
        Tool(
            name="search_memory",
            description="Search enterprise memory (decisions, risks, lessons, supplier history) "
            "for records related to a query.",
            params=[
                ToolParam("query", "str", True, "what to look for"),
                ToolParam("project_id", "int", False, "restrict to one project"),
            ],
            handler=_search_memory,
        ),
        Tool(
            name="search_documents",
            description="Search the document corpus (emails, meeting minutes, reports, "
            "correspondence) with hybrid semantic + keyword retrieval.",
            params=[
                ToolParam("query", "str", True, "what to look for"),
                ToolParam("project_id", "int", False, "restrict to one project"),
            ],
            handler=_search_documents,
        ),
        Tool(
            name="assess_supplier_risk",
            description="Compute a supplier's risk score and recommendation from delivery "
            "history and non-conformance records.",
            params=[ToolParam("supplier_id", "int", True, "the supplier to assess")],
            handler=_supplier_risk,
            # Matches /suppliers/{id}/risk-assessment (RiskRoles).
            allowed_roles=frozenset(
                {Role.ADMIN, Role.EXECUTIVE, Role.PROCUREMENT_OFFICER}
            ),
        ),
        Tool(
            name="review_purchase_request",
            description="Review a purchase request for missing fields, material category, "
            "risk, and the approval route it should follow.",
            params=[ToolParam("pr_id", "int", True, "the purchase request to review")],
            handler=_purchase_request_review,
            # Matches /procurement/purchase-requests/analyze (ProcurementRoles).
            allowed_roles=frozenset(
                {Role.ADMIN, Role.PROCUREMENT_OFFICER, Role.PROJECT_MANAGER}
            ),
        ),
        Tool(
            name="escalate_overdue_rfis",
            description="Find a project's overdue RFIs and draft an escalation message.",
            params=[ToolParam("project_id", "int", True, "the project to check")],
            handler=_rfi_escalation,
            # Matches /rfis/{project_id}/analyze (RfiRoles).
            allowed_roles=frozenset({Role.ADMIN, Role.PROJECT_MANAGER, Role.SITE_ENGINEER}),
        ),
        Tool(
            name="executive_report",
            description="Aggregate portfolio KPIs (delays, overdue RFIs, late POs, open NCRs, "
            "pending PRs) with a management narrative; omit project_id for the whole portfolio.",
            params=[ToolParam("project_id", "int", False, "one project, or all if omitted")],
            handler=_executive_report,
            # Matches /reports/executive-weekly.
            allowed_roles=frozenset({Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER}),
        ),
        Tool(
            name="meeting_summarize",
            description="Summarize meeting notes into a summary, action items, decisions, and "
            "risks for a project. Pass the raw notes text; retrieve it with search_documents "
            "first if it is not already in the goal.",
            params=[
                ToolParam("project_id", "int", True, "the project the meeting belongs to"),
                ToolParam("notes", "str", True, "the raw meeting notes or transcript text"),
            ],
            handler=_meeting_summarize,
            # Matches /meetings/{project_id}/summarize (MeetingRoles).
            allowed_roles=frozenset({Role.ADMIN, Role.PROJECT_MANAGER, Role.QA_QC}),
        ),
        Tool(
            name="analyze_site_report",
            description="Analyze a daily site report for completed work, delays, risks, and "
            "manpower. Pass the raw report text; retrieve it with search_documents first if it "
            "is not already in the goal.",
            params=[
                ToolParam("project_id", "int", True, "the project the report belongs to"),
                ToolParam("text", "str", True, "the raw site report text"),
            ],
            handler=_analyze_site_report,
            # Matches /site-reports/{project_id}/analyze (SiteRoles).
            allowed_roles=frozenset({Role.ADMIN, Role.PROJECT_MANAGER, Role.SITE_ENGINEER}),
        ),
        Tool(
            name="get_project",
            description="Look up a single project's core details by id.",
            params=[ToolParam("project_id", "int", True, "the project id")],
            handler=_get_project,
        ),
        Tool(
            name="get_claims",
            description="List every contract claim on record for a project, with claim number, "
            "type, amount, and status, plus the total claimed value.",
            params=[ToolParam("project_id", "int", True, "the project id")],
            handler=_get_claims,
            # Matches GET /claims (CurrentUser — open to any authenticated role).
        ),
        Tool(
            name="get_change_orders",
            description="List every change order on record for a project, with change order "
            "number, value, and status, plus the total value.",
            params=[ToolParam("project_id", "int", True, "the project id")],
            handler=_get_change_orders,
            # Matches GET /change-orders (CurrentUser — open to any authenticated role).
        ),
        Tool(
            name="get_safety_events",
            description="List every safety event on record for a project, with date, "
            "severity, description, and the corrective action taken.",
            params=[ToolParam("project_id", "int", True, "the project id")],
            handler=_get_safety_events,
            # No REST endpoint exists for this table; open to any agent-eligible role,
            # matching every other read-only operational lookup in this registry.
        ),
        Tool(
            name="get_project_risks",
            description="List a project's risk register — title, severity, likelihood, status, "
            "and owner — highest severity first, with a count of how many remain open.",
            params=[ToolParam("project_id", "int", True, "the project id")],
            handler=_get_project_risks,
            # Matches GET /projects/{id}/risks (CurrentUser — open to any authenticated role).
        ),
        Tool(
            name="get_open_action_items",
            description="List a project's unresolved meeting action items, with owner, due date, "
            "and which ones are overdue.",
            params=[ToolParam("project_id", "int", True, "the project id")],
            handler=_get_open_action_items,
            # Matches GET /meetings/{id}/action-items (CurrentUser — open to any role).
        ),
        Tool(
            name="remember",
            description="Persist a durable finding to enterprise memory so it can be reused in "
            "later work. Category is one of decision, risk, issue, lesson_learned, "
            "supplier_performance, procurement_blocker, safety_event, client_instruction.",
            params=[
                ToolParam("summary", "str", True, "the finding to remember"),
                ToolParam("category", "str", False, "memory category"),
                ToolParam("detail", "str", False, "supporting detail"),
                ToolParam("project_id", "int", False, "related project"),
            ],
            handler=_remember,
        ),
        Tool(
            name="recall_past_sessions",
            description="Search the agent's own previous runs for what it concluded on a topic "
            "before (cross-session recall).",
            params=[ToolParam("query", "str", True, "topic to recall")],
            handler=_recall_past_sessions,
        ),
        Tool(
            name="find_project",
            description="Find project ids by name or code fragment.",
            params=[ToolParam("query", "str", True, "name or code fragment")],
            handler=_find_project,
        ),
    ]
    return {tool.name: tool for tool in tools}
