from datetime import date as date_type
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MemoryCategory(StrEnum):
    DECISION = "decision"
    RISK = "risk"
    ISSUE = "issue"
    LESSON_LEARNED = "lesson_learned"
    SUPPLIER_PERFORMANCE = "supplier_performance"
    PROCUREMENT_BLOCKER = "procurement_blocker"
    SAFETY_EVENT = "safety_event"
    CLIENT_INSTRUCTION = "client_instruction"


class MemoryCreate(BaseModel):
    project_id: int | None = None
    category: MemoryCategory
    summary: str
    detail: str | None = None
    source_type: str | None = None
    source_id: int | None = None
    source_excerpt: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    category: str
    summary: str
    detail: str | None
    source_type: str | None
    source_id: int | None
    source_excerpt: str | None
    confidence: float | None
    created_by: str
    created_at: datetime


class MemorySearchHit(BaseModel):
    memory: MemoryRead
    score: float


class MemorySearchResponse(BaseModel):
    query: str
    count: int
    results: list[MemorySearchHit]


class ExtractedMemory(BaseModel):
    category: MemoryCategory
    summary: str
    detail: str | None = None
    confidence_score: float = Field(ge=0, le=1)
    date: date_type | None = None


class MemoryExtractRequest(BaseModel):
    text: str
    project_id: int | None = None
    source_type: str | None = None
    source_id: int | None = None
    store: bool = False


class MemoryExtractResponse(BaseModel):
    provider: str
    model: str
    extracted: list[ExtractedMemory]
    stored: list[MemoryRead]
