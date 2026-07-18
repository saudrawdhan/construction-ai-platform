"""Construction AI Copilot (spec module 7 + prompt 11.1). Answers management questions grounded
ONLY in retrieved evidence — enterprise memory + the document corpus. Grounding uses full-text
matching on the question's substantive keywords (OR-combined, relevance-ranked) so it genuinely
refuses when no record mentions the topic — pure vector search always returns nearest neighbours
and could never refuse. Deterministic in mock mode; LLM-narrated with the spec assistant prompt
in real mode. The LLM prompt itself is instructed to flag missing evidence. Reports every source.
"""

import re

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.content_shield import shield
from app.agents.prompts import CONSTRUCTION_OPS_ASSISTANT
from app.models import AiMemory, DocumentEmbedding
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
    tokens = re.findall(r"[\w؀-ۿ]+", question.lower())
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


_REFUSAL = (
    "The available project records and enterprise memory do not contain evidence to answer "
    "this question. Missing information: no documents, decisions, or memories mention this "
    "topic. Please refine the question or ingest the related records."
)


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

        memory_ids = await _match_ids(
            db, table="ai_memories", column="summary", tsquery=tsquery,
            project_id=project_id, extra_where="superseded_by_id IS NULL", limit=4,
        )
        document_ids = await _match_ids(
            db, table="document_embeddings", column="content", tsquery=tsquery,
            project_id=project_id, extra_where=None, limit=4,
        )
        if not memory_ids and not document_ids:
            return self._refuse()

        evidence: list[str] = []
        sources: list[CopilotSource] = []
        if memory_ids:
            rows = await db.scalars(select(AiMemory).where(AiMemory.id.in_(memory_ids)))
            for memory in rows:
                # Shield retrieved content the same way the agent's tools do: a poisoned memory
                # or document must reach the LLM wrapped as untrusted, never as plain evidence.
                evidence.append(shield(f"[MEMORY · {memory.category}]", memory.summary))
                sources.append(
                    CopilotSource(type="memory", id=memory.id, label=memory.summary[:80])
                )
        if document_ids:
            rows = await db.scalars(
                select(DocumentEmbedding).where(DocumentEmbedding.id.in_(document_ids))
            )
            for chunk in rows:
                evidence.append(
                    shield(
                        f"[{chunk.source_type} #{chunk.source_id}]",
                        chunk.content,
                        display=chunk.content[:400],
                    )
                )
                sources.append(
                    CopilotSource(
                        type=chunk.source_type, id=chunk.source_id, label=chunk.content[:80]
                    )
                )

        context = "\n\n".join(evidence)
        if self.provider == "mock":
            answer = (
                f"Based on {len(sources)} retrieved source(s): {evidence[0][:280]} "
                "(grounded answer assembled from project records; see sources)."
            )
        else:
            user_content = f"Question: {question}\n\nEvidence:\n{context}"
            result = await self._llm.complete(
                system=CONSTRUCTION_OPS_ASSISTANT,
                messages=[{"role": "user", "content": user_content}],
                max_tokens=800,
            )
            answer = result.text.strip() or _REFUSAL

        return CopilotResult(
            answer=answer, grounded=True, sources=sources,
            provider=self.provider, model=self.model,
        )
