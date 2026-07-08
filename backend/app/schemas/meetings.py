from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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
