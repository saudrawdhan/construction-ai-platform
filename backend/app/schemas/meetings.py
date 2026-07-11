from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MeetingCreate(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=255)
    meeting_type: str = Field(min_length=1, max_length=100)
    meeting_date: date | None = None


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    meeting_type: str | None = Field(default=None, min_length=1, max_length=100)
    meeting_date: date | None = None


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    meeting_date: date | None
    title: str
    meeting_type: str


class MeetingActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    project_id: int
    description: str
    owner: str | None
    due_date: date | None
    status: str
    created_at: datetime


class MeetingDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    meeting_id: int
    decision_date: date | None
    decision_text: str
    owner: str
