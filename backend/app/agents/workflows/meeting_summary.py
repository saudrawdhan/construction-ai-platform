"""Meeting Summary workflow (spec 9). Turns meeting notes into a summary, action items,
decisions, and risks. In mock mode it parses the structured sections construction minutes
already use; in real mode the LLM produces the structured JSON. When stored, it creates the
meeting, its action items, its decisions, and a memory per decision (the reuse loop).
"""

import json
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows.base import gather_memory_context, localize
from app.models import Meeting, MeetingActionItem, ProjectDecision
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import (
    ActionItem,
    DecisionItem,
    MeetingSummarizeRequest,
    MeetingSummary,
)
from app.services.audit import log_ai_call
from app.services.embeddings import get_embedder
from app.services.llm import LLMClient
from app.services.memory import create_memory

_SUMMARIZE_PROMPT = (
    "You summarize construction meeting minutes. Return JSON with keys: summary (string), "
    "action_items (list of {description, owner}), decisions (list of {text, owner}), "
    "risks (list of strings). Use only the provided notes."
)


def _section(lines: list[str], header: str) -> list[str]:
    collected: list[str] = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(header.lower()):
            capturing = True
            continue
        if capturing:
            if stripped.endswith(":") and not stripped.startswith("-"):
                break
            if stripped.startswith("-"):
                collected.append(stripped.lstrip("- ").strip())
    return [item for item in collected if item]


def _split_owner(text: str) -> tuple[str, str | None]:
    if "Owner:" in text:
        body, owner = text.split("Owner:", 1)
        return body.strip().rstrip("."), owner.strip() or None
    return text.strip(), None


def _heuristic(notes: str) -> tuple[str, list[ActionItem], list[DecisionItem], list[str]]:
    lines = notes.splitlines()
    summary_lines = _section(lines, "Discussion Summary")
    summary = " ".join(summary_lines) if summary_lines else " ".join(notes.split())[:400]
    decisions = []
    for entry in _section(lines, "Decision"):
        body, owner = _split_owner(entry)
        decisions.append(DecisionItem(text=body, owner=owner))
    actions = []
    for entry in _section(lines, "Action"):
        body, owner = _split_owner(entry)
        actions.append(ActionItem(description=body, owner=owner))
    risks = [
        " ".join(line.split())
        for line in lines
        if any(cue in line.lower() for cue in ("risk", "delay", "critical path"))
    ][:5]
    return summary, actions, decisions, risks


def _parse_llm(raw: str):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    summary = str(data.get("summary", ""))
    actions = [
        ActionItem(description=str(a.get("description", "")), owner=a.get("owner"))
        for a in data.get("action_items", [])
        if isinstance(a, dict) and a.get("description")
    ]
    decisions = [
        DecisionItem(text=str(d.get("text", "")), owner=d.get("owner"))
        for d in data.get("decisions", [])
        if isinstance(d, dict) and d.get("text")
    ]
    risks = [str(r) for r in data.get("risks", []) if r]
    return summary, actions, decisions, risks


async def run(
    db: AsyncSession, *, project_id: int, payload: MeetingSummarizeRequest, llm: LLMClient,
    language: str = "en",
) -> MeetingSummary:
    memory_context, memory_ids = await gather_memory_context(
        db, query=payload.notes[:300], project_id=project_id, k=3
    )

    summary, actions, decisions, risks = _heuristic(payload.notes)
    if llm.provider != "mock":
        user_content = f"{payload.notes}\n\nContext:\n{memory_context}"
        result = await llm.complete(
            system=localize(_SUMMARIZE_PROMPT, language, json_mode=True),
            messages=[{"role": "user", "content": user_content}],
            json_mode=True,
            max_tokens=1500,
        )
        parsed = _parse_llm(result.text)
        if parsed and parsed[0]:
            summary, actions, decisions, risks = parsed

    meeting_id: int | None = None
    stored_actions = 0
    stored_decisions = 0
    if payload.store:
        meeting = Meeting(
            project_id=project_id,
            meeting_date=payload.meeting_date or date.today(),
            title=payload.title,
            meeting_type=payload.meeting_type,
        )
        db.add(meeting)
        await db.flush()
        meeting_id = meeting.id

        for action in actions:
            db.add(
                MeetingActionItem(
                    meeting_id=meeting.id,
                    project_id=project_id,
                    description=action.description,
                    owner=action.owner,
                    due_date=action.due_date,
                    status="Open",
                )
            )
            stored_actions += 1

        embedder = get_embedder()
        for decision in decisions:
            db.add(
                ProjectDecision(
                    project_id=project_id,
                    meeting_id=meeting.id,
                    decision_date=payload.meeting_date or date.today(),
                    decision_text=decision.text,
                    owner=decision.owner or "Unassigned",
                )
            )
            stored_decisions += 1
            await create_memory(
                db,
                embedder,
                MemoryCreate(
                    project_id=project_id,
                    category=MemoryCategory.DECISION,
                    summary=decision.text,
                    source_type="meeting",
                    source_id=meeting.id,
                    confidence=0.85,
                ),
                created_by="agent",
            )

    await log_ai_call(
        db,
        workflow="meeting_summary",
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
        source_ids={"project": project_id, "meeting": meeting_id, "memory": memory_ids},
        output_excerpt=summary,
    )

    return MeetingSummary(
        project_id=project_id,
        summary=summary,
        action_items=actions,
        decisions=decisions,
        risks=risks,
        meeting_id=meeting_id,
        stored_action_items=stored_actions,
        stored_decisions=stored_decisions,
        memory_used=memory_ids,
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
    )
