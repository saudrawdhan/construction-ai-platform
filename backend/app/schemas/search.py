from pydantic import BaseModel


class SearchHit(BaseModel):
    id: int
    source_type: str
    source_id: int
    project_id: int | None
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchHit]
