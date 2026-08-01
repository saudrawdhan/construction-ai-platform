from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Rfi(Base):
    __tablename__ = "rfis"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    rfi_number: Mapped[str] = mapped_column(String(50), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(Text)
    discipline: Mapped[str] = mapped_column(String(100), index=True)
    raised_by: Mapped[str] = mapped_column(String(255))
    assigned_to: Mapped[str] = mapped_column(String(255))
    raised_date: Mapped[date | None] = mapped_column(Date, index=True)
    required_date: Mapped[date | None] = mapped_column(Date, index=True)
    response_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), index=True)
    priority: Mapped[str] = mapped_column(String(50), index=True)


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    co_number: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column(Numeric(16, 2))
    status: Mapped[str] = mapped_column(String(50), index=True)
    # What triggered the change and what it costs in time. `value` already carries the cost
    # impact; without these a change order records only that something changed, leaving no way
    # to answer who caused it or what it did to the programme — the two questions a commercial
    # claim ultimately rests on.
    cause_rfi_id: Mapped[int | None] = mapped_column(ForeignKey("rfis.id"), index=True)
    cause_category: Mapped[str | None] = mapped_column(String(50), index=True)
    cause_description: Mapped[str | None] = mapped_column(Text)
    schedule_impact_days: Mapped[int | None] = mapped_column(Integer)


class Ncr(Base):
    __tablename__ = "ncrs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id"), index=True
    )
    ncr_type: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(50), index=True)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    subcontractor_id: Mapped[int] = mapped_column(ForeignKey("subcontractors.id"), index=True)
    event_date: Mapped[date | None] = mapped_column(Date, index=True)
    severity: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(Text)
    corrective_action: Mapped[str] = mapped_column(Text)
