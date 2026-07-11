from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SiteReportCreate(BaseModel):
    project_id: int
    weather: str = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1)
    report_date: date | None = None


class SiteReportUpdate(BaseModel):
    weather: str | None = Field(default=None, min_length=1, max_length=50)
    summary: str | None = Field(default=None, min_length=1)
    report_date: date | None = None


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
