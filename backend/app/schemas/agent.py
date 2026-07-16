from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)
    project_id: int | None = None
    conversation_id: int | None = None


class SkillRunRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)
    project_id: int | None = None
    conversation_id: int | None = None


class AgentRunSummary(BaseModel):
    id: int
    goal: str
    status: str
    step_count: int
    skill_used: str | None = None
    skill_created: str | None = None
    provider: str
    created_at: datetime


class AgentStepOut(BaseModel):
    index: int
    thought: str
    tool: str
    args: dict
    observation: str
    sources: list[dict] = []


class AgentRunResult(BaseModel):
    id: int | None = None
    goal: str
    status: str
    final_answer: str
    steps: list[AgentStepOut]
    sources: list[dict]
    step_count: int
    skill_used: str | None = None
    skill_created: str | None = None
    provider: str
    model: str
    conversation_id: int | None = None


class SkillStatusUpdate(BaseModel):
    status: Literal["active", "deprecated"]


class SkillRead(BaseModel):
    id: int
    name: str
    description: str
    parameters: list
    plan: list
    usage_count: int
    success_count: int
    success_rate: float
    status: str
    version: int

    @classmethod
    def from_model(cls, skill) -> "SkillRead":
        usage = skill.usage_count or 0
        success = skill.success_count or 0
        rate = round(success / usage, 2) if usage else 0.0
        return cls(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            parameters=skill.parameters or [],
            plan=skill.plan or [],
            usage_count=usage,
            success_count=success,
            success_rate=rate,
            status=skill.status,
            version=skill.version,
        )
