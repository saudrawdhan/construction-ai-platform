from pydantic import BaseModel, Field


class CopilotChatRequest(BaseModel):
    question: str = Field(min_length=3)
    project_id: int | None = None
    conversation_id: int | None = None


class CopilotSource(BaseModel):
    type: str  # memory | document | correspondence
    id: int | None
    label: str


class CopilotAnswer(BaseModel):
    conversation_id: int
    question: str
    answer: str
    grounded: bool
    sources: list[CopilotSource]
    provider: str
    model: str
