from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    doc_type: str
    title: str
    doc_date: date | None
    content_summary: str
    original_filename: str | None = None
    # Populated from the ORM object but never serialized — the client only ever sees
    # has_file, never the server's own filesystem path.
    storage_path: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_file(self) -> bool:
        return self.storage_path is not None


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
