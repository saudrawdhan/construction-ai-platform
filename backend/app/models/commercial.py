from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    claim_number: Mapped[str] = mapped_column(String(50), index=True)
    claim_type: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[float] = mapped_column(Numeric(16, 2))
    status: Mapped[str] = mapped_column(String(50), index=True)
    narrative: Mapped[str] = mapped_column(Text)


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    change_order_id: Mapped[int] = mapped_column(ForeignKey("change_orders.id"), index=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("project_decisions.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    correspondence_id: Mapped[int] = mapped_column(ForeignKey("correspondence.id"), index=True)
    evidence_note: Mapped[str] = mapped_column(Text)


class Correspondence(Base):
    __tablename__ = "correspondence"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    related_record_type: Mapped[str] = mapped_column(String(50), index=True)
    related_record_id: Mapped[int] = mapped_column(Integer, index=True)
    sent_date: Mapped[date | None] = mapped_column(Date, index=True)
    sender: Mapped[str] = mapped_column(String(255))
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
