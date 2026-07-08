from datetime import date

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    doc_type: str
    title: str
    doc_date: date | None
    content_summary: str


class DocumentUploadResult(BaseModel):
    document_id: int
    project_id: int
    title: str
    doc_type: str
    characters: int
    chunks_indexed: int
    embedding_provider: str


class GeneratedDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    type: str
    project_id: int
    related_record_id: int
    document_date: date | None
    sender: str | None
    recipient: str | None
    subject: str
    body: str
