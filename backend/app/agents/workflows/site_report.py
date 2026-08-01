"""Daily Site Report workflow (spec 9). Extracts completed work, delays, risks, a manpower
note, and a recommended escalation from a daily report. Mock mode uses sentence-level
keyword heuristics; real mode uses the LLM. Detected delays/risks are written to memory.
"""

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows.base import gather_memory_context, localize
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import SiteReportAnalysis, SiteReportAnalyzeRequest
from app.services.audit import log_ai_call
from app.services.embeddings import get_embedder
from app.services.llm import LLMClient
from app.services.memory import create_memory

_ANALYZE_PROMPT = (
    "You analyze a construction daily site report. Return JSON with keys: summary, "
    "completed_work (list), delays (list), risks (list), manpower_note (string), "
    "recommended_escalation (string). Use only the report text."
)

_COMPLETED = ("completed", "progressed", "finished", "installed", "poured", "erected")
_DELAY = ("delay", "late", "pending", "waiting", "behind", "not delivered", "on hold")
_RISK = ("risk", "impact", "unsafe", "shortage", "stoppage", "escalat")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!؟\n])\s+", " ".join(text.split()))
    return [p.strip() for p in parts if p.strip()]


def _match(sentences: list[str], cues: tuple[str, ...]) -> list[str]:
    return [s for s in sentences if any(cue in s.lower() for cue in cues)][:5]


def _heuristic(text: str):
    sentences = _sentences(text)
    completed = _match(sentences, _COMPLETED)
    delays = _match(sentences, _DELAY)
    risks = _match(sentences, _RISK)
    manpower = next((s for s in sentences if "manpower" in s.lower() or "crew" in s.lower()), None)
    summary = " ".join(sentences[:2]) if sentences else " ".join(text.split())[:300]
    if delays or risks:
        escalation = (
            "Escalate the identified delays/risks to the project manager for corrective "
            "action before the next shift."
        )
    else:
        escalation = "No escalation required; progress is on track."
    return summary, completed, delays, risks, manpower, escalation


def _parse_llm(raw: str):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return (
        str(data.get("summary", "")),
        [str(x) for x in data.get("completed_work", []) if x],
        [str(x) for x in data.get("delays", []) if x],
        [str(x) for x in data.get("risks", []) if x],
        data.get("manpower_note"),
        str(data.get("recommended_escalation", "")),
    )


async def run(
    db: AsyncSession, *, project_id: int, payload: SiteReportAnalyzeRequest, llm: LLMClient,
    language: str = "en",
) -> SiteReportAnalysis:
    memory_context, memory_ids = await gather_memory_context(
        db, query=payload.text[:300], project_id=project_id, k=3
    )

    summary, completed, delays, risks, manpower, escalation = _heuristic(payload.text)
    if llm.provider != "mock":
        result = await llm.complete(
            system=localize(_ANALYZE_PROMPT, language, json_mode=True),
            messages=[{"role": "user", "content": f"{payload.text}\n\nContext:\n{memory_context}"}],
            json_mode=True,
            max_tokens=1200,
        )
        parsed = _parse_llm(result.text)
        if parsed and parsed[0]:
            summary, completed, delays, risks, manpower, escalation = parsed

    if payload.store and (delays or risks):
        detail = "; ".join(delays + risks)[:400]
        await create_memory(
            db,
            get_embedder(),
            MemoryCreate(
                project_id=project_id,
                category=MemoryCategory.RISK if risks else MemoryCategory.ISSUE,
                summary=f"Site report flagged: {detail}",
                source_type="site_report",
                confidence=0.6,
            ),
            created_by="agent",
        )

    await log_ai_call(
        db,
        workflow="site_report_analysis",
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
        source_ids={"project": project_id, "memory": memory_ids},
        output_excerpt=summary,
    )

    return SiteReportAnalysis(
        project_id=project_id,
        summary=summary,
        completed_work=completed,
        delays=delays,
        risks=risks,
        manpower_note=manpower,
        recommended_escalation=escalation,
        memory_used=memory_ids,
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
    )
