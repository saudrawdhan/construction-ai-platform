from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApprovalCreate(BaseModel):
    action_type: str
    project_id: int | None = None
    payload: dict | None = None
    risk_level: str = "high"


class ApprovalDecision(BaseModel):
    note: str | None = None


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    action_type: str
    payload: dict | None
    risk_level: str
    requested_by: str
    status: str
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime


class ApprovalHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    approval_request_id: int
    actor: str
    action: str
    note: str | None
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    channel: str
    title: str
    body: str
    category: str | None
    is_read: bool
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    workflow: str
    provider: str
    model: str
    source_ids: dict | None
    output_excerpt: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
