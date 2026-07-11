from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class RfiCreate(BaseModel):
    project_id: int
    rfi_number: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1)
    discipline: str = Field(min_length=1, max_length=100)
    raised_by: str = Field(min_length=1, max_length=255)
    assigned_to: str = Field(min_length=1, max_length=255)
    raised_date: date | None = None
    required_date: date | None = None
    status: str = "Open"
    priority: str = "Medium"


class RfiUpdate(BaseModel):
    rfi_number: str | None = Field(default=None, min_length=1, max_length=50)
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    question: str | None = Field(default=None, min_length=1)
    discipline: str | None = Field(default=None, min_length=1, max_length=100)
    raised_by: str | None = Field(default=None, min_length=1, max_length=255)
    assigned_to: str | None = Field(default=None, min_length=1, max_length=255)
    raised_date: date | None = None
    required_date: date | None = None
    status: str | None = None
    priority: str | None = None


class RfiRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    rfi_number: str
    subject: str
    question: str
    discipline: str
    raised_by: str
    assigned_to: str
    raised_date: date | None
    required_date: date | None
    response_date: date | None
    status: str
    priority: str
