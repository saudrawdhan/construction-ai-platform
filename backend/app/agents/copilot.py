"""Construction AI Copilot (spec module 7 + prompt 11.1). Answers management questions grounded
ONLY in retrieved evidence — enterprise memory, the document corpus, and the structured
operational registers the brief names directly (project risks, recorded decisions, open meeting
action items).
Grounding uses full-text matching on the question's substantive keywords (OR-combined,
relevance-ranked) so it genuinely refuses when no record mentions the topic — pure vector search
always returns nearest neighbours and could never refuse. Deterministic in mock mode;
LLM-narrated with the spec assistant prompt in real mode. Reports every source, each tagged with
the project it belongs to.
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.content_shield import shield
from app.agents.prompts import CONSTRUCTION_OPS_ASSISTANT
from app.models import (
    AiMemory,
    DocumentEmbedding,
    MeetingActionItem,
    Project,
    ProjectDecision,
    ProjectRisk,
)
from app.schemas.copilot import CopilotSource
from app.services.llm import LLMClient

# Full-text ANDs terms by default; natural-language filler would then block every match. Strip
# common English question/stop words to substantive keywords (Arabic kept as-is), then OR them.
_STOPWORDS = frozenset(
    "the a an is are was were be been being of to in on at by for with and or not do does did "
    "why what how when where which who whom that this these those it its we our you your i me my "
    "will would can could should has have had any some all more most about into over under then "
    "than as status show tell give list please affecting affected".split()
)


def _keyword_tsquery(question: str) -> str:
    # `\w` is Unicode-aware, so it already matches Arabic letters while correctly excluding Arabic
    # punctuation. An explicit U+0600-U+06FF range was previously added alongside it, which also
    # swept in ؟ ، ؛ ٪ — so a question ending in the Arabic question mark (i.e. every natural one)
    # produced a corrupted final token such as "المخاطر؟" that matches nothing. Do not re-add it.
    tokens = re.findall(r"\w+", question.lower())
    terms = [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]
    return " | ".join(dict.fromkeys(terms))  # de-duplicate, keep order


async def _match_ids(
    db: AsyncSession, *, table: str, column: str, tsquery: str, project_id: int | None,
    extra_where: str | None, limit: int,
) -> list[int]:
    where = f"to_tsvector('simple', {column}) @@ to_tsquery('simple', :q)"
    if project_id is not None:
        where += " AND project_id = :pid"
    if extra_where:
        where += f" AND {extra_where}"
    sql = text(
        f"SELECT id FROM {table} WHERE {where} "
        f"ORDER BY ts_rank(to_tsvector('simple', {column}), to_tsquery('simple', :q)) DESC "
        "LIMIT :lim"
    )
    params: dict = {"q": tsquery, "lim": limit}
    if project_id is not None:
        params["pid"] = project_id
    result = await db.execute(sql, params)
    return [row[0] for row in result]


# `position(... in ...)` is a plain substring test with none of ILIKE's wildcard semantics, so a
# project whose name legitimately contains % or _ cannot turn into a pattern that matches
# everything. Ordering is applied in Python because ties matter — see _identify_project.
_PROJECT_MENTION_SQL = text(
    "SELECT id, project_code, project_name FROM projects "
    "WHERE position(lower(project_code) in lower(:q)) > 0 "
    "   OR position(lower(project_name) in lower(:q)) > 0"
)

_REFUSAL = (
    "The available project records and enterprise memory do not contain evidence to answer "
    "this question. Missing information: no documents, decisions, or memories mention this "
    "topic. Please refine the question or ingest the related records."
)


@dataclass
class _Evidence:
    """One retrieved record, carrying the project it belongs to so the narrator can never
    silently attribute it to a different one."""

    kind: str
    source_id: int
    project_id: int | None
    heading: str
    body: str
    label: str
    display: str | None = None


def _project_label(project: Project | None, project_id: int | None) -> str:
    if project is not None:
        return f"{project.project_code} — {project.project_name}"
    return f"project {project_id}" if project_id is not None else "no project"


async def _identify_project(db: AsyncSession, question: str) -> tuple[int, str] | None:
    """Resolve a project named in the question itself. The UI does not always send an explicit
    project_id, and a question that names a project must not be answered from the whole
    portfolio — live testing showed exactly that failure, with three of four cited sources
    belonging to other projects while the narrative presented them as the named one's.

    The longest match wins, because one project's name can legitimately be a prefix of
    another's ("Riyadh Infrastructure Project 1" inside "... Project 11"); a tie is genuinely
    ambiguous and scopes nothing rather than guessing.
    """
    rows = list(await db.execute(_PROJECT_MENTION_SQL, {"q": question}))
    if not rows:
        return None
    longest = max(len(row.project_name) for row in rows)
    best = [row for row in rows if len(row.project_name) == longest]
    if len(best) != 1:
        return None
    match = best[0]
    return int(match.id), f"{match.project_code} — {match.project_name}"


async def _gather(
    db: AsyncSession, *, tsquery: str, project_id: int | None
) -> list[_Evidence]:
    """Collect matching evidence from every grounded source. Memory stays first so the most
    condensed, highest-signal records lead the context window."""
    found: list[_Evidence] = []

    memory_ids = await _match_ids(
        db, table="ai_memories", column="summary", tsquery=tsquery,
        project_id=project_id, extra_where="superseded_by_id IS NULL", limit=4,
    )
    if memory_ids:
        for memory in await db.scalars(select(AiMemory).where(AiMemory.id.in_(memory_ids))):
            found.append(
                _Evidence(
                    kind="memory", source_id=memory.id, project_id=memory.project_id,
                    heading=f"MEMORY · {memory.category}",
                    # Include detail, not just summary — the substantive "why" lives there when
                    # present, and discarding it made every grounded answer blind to it (proven
                    # live: the copilot reported a stored reason as "not available").
                    body=(
                        f"{memory.summary}\n{memory.detail}" if memory.detail else memory.summary
                    ),
                    label=memory.summary[:80],
                )
            )

    document_ids = await _match_ids(
        db, table="document_embeddings", column="content", tsquery=tsquery,
        project_id=project_id, extra_where=None, limit=4,
    )
    if document_ids:
        rows = await db.scalars(
            select(DocumentEmbedding).where(DocumentEmbedding.id.in_(document_ids))
        )
        for chunk in rows:
            found.append(
                _Evidence(
                    kind=chunk.source_type, source_id=chunk.source_id,
                    project_id=chunk.project_id,
                    heading=f"{chunk.source_type} #{chunk.source_id}", body=chunk.content,
                    label=chunk.content[:80], display=chunk.content[:400],
                )
            )

    # The brief's copilot module names "risk" and "unresolved action items" as questions this
    # surface must answer; grounding on memory and documents alone could only answer them by
    # coincidence, whenever the fact happened to have been written down somewhere else.
    risk_ids = await _match_ids(
        db, table="project_risks",
        column="coalesce(title, '') || ' ' || coalesce(description, '')",
        tsquery=tsquery, project_id=project_id, extra_where=None, limit=3,
    )
    if risk_ids:
        for risk in await db.scalars(select(ProjectRisk).where(ProjectRisk.id.in_(risk_ids))):
            body = f"{risk.title}. {risk.description}" if risk.description else risk.title
            found.append(
                _Evidence(
                    kind="project_risk", source_id=risk.id, project_id=risk.project_id,
                    heading=(
                        f"RISK · {risk.severity} severity · status {risk.status} · "
                        f"owner {risk.owner or 'unassigned'}"
                    ),
                    body=body, label=risk.title[:80],
                )
            )

    # Brief §2.2 names this as a business problem in its own words: "Decision history is rarely
    # searchable: who approved what, when, why". The decisions are recorded by the meeting
    # workflow, so without this the record existed but no question could reach it.
    decision_ids = await _match_ids(
        db, table="project_decisions", column="decision_text", tsquery=tsquery,
        project_id=project_id, extra_where=None, limit=3,
    )
    if decision_ids:
        rows = await db.scalars(
            select(ProjectDecision).where(ProjectDecision.id.in_(decision_ids))
        )
        for decision in rows:
            found.append(
                _Evidence(
                    kind="project_decision", source_id=decision.id,
                    project_id=decision.project_id,
                    heading=(
                        f"DECISION · {decision.decision_date or 'undated'} · "
                        f"owner {decision.owner}"
                    ),
                    body=decision.decision_text, label=decision.decision_text[:80],
                )
            )

    action_ids = await _match_ids(
        db, table="meeting_action_items", column="description", tsquery=tsquery,
        project_id=project_id, extra_where=None, limit=3,
    )
    if action_ids:
        rows = await db.scalars(
            select(MeetingActionItem).where(MeetingActionItem.id.in_(action_ids))
        )
        for item in rows:
            found.append(
                _Evidence(
                    kind="meeting_action_item", source_id=item.id, project_id=item.project_id,
                    heading=(
                        f"ACTION ITEM · status {item.status} · owner "
                        f"{item.owner or 'unassigned'} · due {item.due_date or 'no date'}"
                    ),
                    body=item.description, label=item.description[:80],
                )
            )

    return found


class CopilotResult(BaseModel):
    answer: str
    grounded: bool
    sources: list[CopilotSource]
    provider: str
    model: str


class ConstructionCopilot:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self.provider = llm.provider
        self.model = getattr(llm, "model", "unknown")

    def _refuse(self) -> CopilotResult:
        return CopilotResult(
            answer=_REFUSAL, grounded=False, sources=[],
            provider=self.provider, model=self.model,
        )

    async def answer(
        self, db: AsyncSession, *, question: str, project_id: int | None = None
    ) -> CopilotResult:
        tsquery = _keyword_tsquery(question)
        if not tsquery:
            return self._refuse()

        scope: tuple[int, str] | None = None
        if project_id is not None:
            project = await db.get(Project, project_id)
            scope = (project_id, _project_label(project, project_id))
        else:
            scope = await _identify_project(db, question)

        scoped = await _gather(db, tsquery=tsquery, project_id=scope[0]) if scope else []
        # Falling back to the whole portfolio keeps a genuinely useful answer available when the
        # named project has nothing on file, but the shortfall is stated as a computed fact and
        # every borrowed record is marked, so "no data for this project" can never be narrated
        # into "here is that project's data".
        evidence = scoped or await _gather(db, tsquery=tsquery, project_id=None)
        if not evidence:
            return self._refuse()

        borrowed = bool(scope) and not scoped
        lead = (
            f"No records on file for {scope[1]} match this question. "
            "The evidence below belongs to other projects and is offered only as related "
            "context." if borrowed and scope else None
        )

        project_ids = {e.project_id for e in evidence if e.project_id is not None}
        names: dict[int, Project] = {}
        if project_ids:
            rows = await db.scalars(select(Project).where(Project.id.in_(project_ids)))
            names = {p.id: p for p in rows}

        blocks: list[str] = []
        sources: list[CopilotSource] = []
        for item in evidence:
            where = _project_label(names.get(item.project_id), item.project_id)
            foreign = (
                scope is not None
                and item.project_id is not None
                and item.project_id != scope[0]
            )
            marker = " · OTHER PROJECT — not the project asked about" if foreign else ""
            # Shield retrieved content the same way the agent's tools do: a poisoned memory,
            # document, or register entry must reach the LLM wrapped as untrusted, never as
            # plain evidence. The project tag is part of the label so attribution survives
            # even when the shield rewrites the line.
            blocks.append(
                shield(f"[{item.heading} · {where}{marker}]", item.body, display=item.display)
            )
            sources.append(
                CopilotSource(
                    type=item.kind, id=item.source_id, label=item.label,
                    project_id=item.project_id,
                    project_label=None if item.project_id is None else where,
                )
            )

        context = "\n\n".join(blocks)
        if self.provider == "mock":
            narration = (
                f"Based on {len(sources)} retrieved source(s): {blocks[0][:280]} "
                "(grounded answer assembled from project records; see sources)."
            )
        else:
            # The shortfall is prepended verbatim as a computed fact, so the model is told not
            # to restate it — the same "do not restate what is already stated exactly" rule the
            # workflow narrative prompts use to stop a model paraphrasing an authoritative line.
            instruction = (
                f"\n\nIMPORTANT: {lead} That sentence is already shown verbatim above your "
                "answer — do not repeat or paraphrase it. Start directly with what the related "
                "evidence shows, and never describe any of it as belonging to the project "
                "asked about.\n\n" if lead else "\n\n"
            )
            # A question carries its own language, so the answer mirrors the question rather than
            # the interface setting — asking in Arabic inside an English UI should still answer in
            # Arabic. This was previously left to emerge on its own, which is not something a
            # small local model reliably does.
            user_content = (
                f"Question: {question}{instruction}Evidence:\n{context}\n\n"
                "Write your entire answer in the same language as the question above, including "
                "any numbers — do not switch language mid-answer. Record identifiers and codes "
                "stay exactly as written."
            )
            result = await self._llm.complete(
                system=CONSTRUCTION_OPS_ASSISTANT,
                messages=[{"role": "user", "content": user_content}],
                max_tokens=800,
            )
            narration = result.text.strip() or _REFUSAL

        return CopilotResult(
            answer=f"{lead}\n\n{narration}" if lead else narration,
            # A question about a named project that no record covers is not grounded in that
            # project, however much adjacent material exists — reporting otherwise would make
            # the fallback indistinguishable from a real answer.
            grounded=not borrowed,
            sources=sources,
            provider=self.provider, model=self.model,
        )
