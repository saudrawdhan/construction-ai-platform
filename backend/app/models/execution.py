from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SiteReport(Base):
    __tablename__ = "site_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    report_date: Mapped[date | None] = mapped_column(Date, index=True)
    weather: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)


class DailyActivity(Base):
    __tablename__ = "daily_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    subcontractor_id: Mapped[int] = mapped_column(ForeignKey("subcontractors.id"), index=True)
    site_report_id: Mapped[int] = mapped_column(ForeignKey("site_reports.id"), index=True)
    activity_date: Mapped[date | None] = mapped_column(Date, index=True)
    activity_description: Mapped[str] = mapped_column(Text)
    manpower_count: Mapped[int] = mapped_column(Integer)


class PlannedActivity(Base):
    __tablename__ = "planned_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    activity_category: Mapped[str] = mapped_column(String(100), index=True)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_finish: Mapped[date | None] = mapped_column(Date)
    planned_manpower: Mapped[int] = mapped_column(Integer, default=0)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
