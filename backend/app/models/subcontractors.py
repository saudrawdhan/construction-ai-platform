from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Subcontractor(Base):
    __tablename__ = "subcontractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    trade: Mapped[str] = mapped_column(String(100), index=True)
    contact_person: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(255))
    classification: Mapped[str] = mapped_column(String(50))
    city: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[date | None] = mapped_column(Date)


class SubcontractorEvaluation(Base):
    __tablename__ = "subcontractor_evaluations"
    __table_args__ = (
        CheckConstraint("quality_score BETWEEN 0 AND 100", name="ck_subeval_quality"),
        CheckConstraint("safety_score BETWEEN 0 AND 100", name="ck_subeval_safety"),
        CheckConstraint("schedule_score BETWEEN 0 AND 100", name="ck_subeval_schedule"),
        CheckConstraint("manpower_score BETWEEN 0 AND 100", name="ck_subeval_manpower"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subcontractor_id: Mapped[int] = mapped_column(ForeignKey("subcontractors.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    evaluation_date: Mapped[date | None] = mapped_column(Date)
    quality_score: Mapped[int] = mapped_column(Integer)
    safety_score: Mapped[int] = mapped_column(Integer)
    schedule_score: Mapped[int] = mapped_column(Integer)
    manpower_score: Mapped[int] = mapped_column(Integer)
    overall_rating: Mapped[float] = mapped_column(Numeric(5, 2))
    comments: Mapped[str | None] = mapped_column(Text)
    linked_safety_event_id: Mapped[int | None] = mapped_column(ForeignKey("safety_events.id"))
    linked_ncr_id: Mapped[int | None] = mapped_column(ForeignKey("ncrs.id"))
    linked_daily_activity_id: Mapped[int | None] = mapped_column(ForeignKey("daily_activities.id"))
