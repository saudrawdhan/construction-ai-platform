from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    project_code: str
    project_name: str
    project_type: str
    client_name: str
    city: str
    start_date: date | None = None
    planned_finish: date | None = None
    actual_finish: date | None = None
    status: str
    budget: Decimal


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    project_code: str | None = None
    project_name: str | None = None
    project_type: str | None = None
    client_name: str | None = None
    city: str | None = None
    start_date: date | None = None
    planned_finish: date | None = None
    actual_finish: date | None = None
    status: str | None = None
    budget: Decimal | None = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None = None


class ProjectRiskCreate(BaseModel):
    title: str
    description: str | None = None
    severity: str
    likelihood: str | None = None
    owner: str | None = None


class ProjectRiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str | None = None
    severity: str
    likelihood: str | None = None
    status: str
    owner: str | None = None
    created_at: datetime
