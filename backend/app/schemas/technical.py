from datetime import date

from pydantic import BaseModel, ConfigDict


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
