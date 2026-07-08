"""Memory Extraction Agent (spec section 11.3). Produces categorized, confidence-scored
memories from operational text. In mock mode (tests/dev) it uses a deterministic keyword
heuristic so the memory pipeline runs offline with no quota; with a real provider it calls
the LLM using the specification prompt and parses/validates the JSON response.
"""

import json
from datetime import date

from pydantic import BaseModel, ValidationError

from app.agents.prompts import MEMORY_EXTRACTION_AGENT
from app.schemas.memory import ExtractedMemory, MemoryCategory
from app.services.llm import LLMClient

# Ordered so extraction is deterministic. Each category maps to lowercase trigger phrases.
_CUES: list[tuple[MemoryCategory, tuple[str, ...]]] = [
    (MemoryCategory.SAFETY_EVENT,
     ("unsafe", "safety", "incident", "near miss", "harness", "scaffold")),
    (MemoryCategory.PROCUREMENT_BLOCKER,
     ("late delivery", "material delay", "long-lead", "expedite", "procurement")),
    (MemoryCategory.DECISION,
     ("decision", "agreed", "approved", "resolved to")),
    (MemoryCategory.CLIENT_INSTRUCTION,
     ("client instruct", "engineer instruct", "owner requires", "client representative")),
    (MemoryCategory.SUPPLIER_PERFORMANCE,
     ("supplier delay", "supplier quality", "supplier reliability")),
    (MemoryCategory.ISSUE,
     ("ncr", "nonconformance", "non-conformance", "defect")),
    (MemoryCategory.RISK,
     ("risk", "critical path", "cost impact", "delay event")),
    (MemoryCategory.LESSON_LEARNED,
     ("lesson learned", "recommend", "should have", "in future")),
]

_MAX_MEMORIES = 3


class ExtractionResult(BaseModel):
    memories: list[ExtractedMemory]
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class MemoryExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self.provider = llm.provider
        self.model = getattr(llm, "model", "unknown")

    async def extract(self, *, text: str, source_date: date | None = None) -> ExtractionResult:
        if self.provider == "mock":
            return ExtractionResult(
                memories=self._heuristic(text, source_date),
                provider=self.provider,
                model=self.model,
            )
        result = await self._llm.complete(
            system=MEMORY_EXTRACTION_AGENT,
            messages=[{"role": "user", "content": text}],
            json_mode=True,
            max_tokens=2048,
        )
        return ExtractionResult(
            memories=self._parse(result.text, source_date),
            provider=self.provider,
            model=self.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )

    def _heuristic(self, text: str, source_date: date | None) -> list[ExtractedMemory]:
        lowered = text.lower()
        memories: list[ExtractedMemory] = []
        for category, cues in _CUES:
            hit = next((cue for cue in cues if cue in lowered), None)
            if hit is None:
                continue
            position = lowered.find(hit)
            snippet = " ".join(text[max(position - 40, 0) : position + 120].split())
            memories.append(
                ExtractedMemory(
                    category=category,
                    summary=f"{category.value.replace('_', ' ').capitalize()}: {snippet}",
                    detail=" ".join(text.split())[:400],
                    confidence_score=0.55,
                    date=source_date,
                )
            )
            if len(memories) >= _MAX_MEMORIES:
                break
        return memories

    def _parse(self, raw: str, source_date: date | None) -> list[ExtractedMemory]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        items = payload.get("memories", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []
        memories: list[ExtractedMemory] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item.setdefault("date", source_date.isoformat() if source_date else None)
            try:
                memories.append(ExtractedMemory.model_validate(item))
            except ValidationError:
                continue
        return memories
