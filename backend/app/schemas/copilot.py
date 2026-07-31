from pydantic import BaseModel, Field


class CopilotChatRequest(BaseModel):
    question: str = Field(min_length=3)
    project_id: int | None = None
    conversation_id: int | None = None


class CopilotSource(BaseModel):
    type: str  # memory | document | correspondence | project_risk | meeting_action_item
    id: int | None
    label: str
    # Which project the cited record actually belongs to. Surfaced so a reader can tell at a
    # glance when an answer is drawing on a project other than the one they asked about.
    project_id: int | None = None
    project_label: str | None = None


class CopilotAnswer(BaseModel):
    conversation_id: int
    question: str
    answer: str
    grounded: bool
    sources: list[CopilotSource]
    provider: str
    model: str
