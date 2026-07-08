from datetime import date

from pydantic import BaseModel, ConfigDict


class SiteReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    report_date: date | None
    weather: str
    summary: str


class DailyActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    subcontractor_id: int
    site_report_id: int
    activity_date: date | None
    activity_description: str
    manpower_count: int
