from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import TimestampMixin


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    # The record this approval decides the fate of. Without it an approval is only a logged
    # verdict: approving a purchase request left the request itself sitting untouched, so the
    # decision never actually moved any work forward. Nullable because some approvals (an
    # advisory risk mitigation, say) genuinely have no single record whose state should change.
    subject_type: Mapped[str | None] = mapped_column(String(50), index=True)
    subject_id: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(50), index=True)
    requested_by: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalHistory(Base, TimestampMixin):
    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    approval_request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_requests.id"), index=True
    )
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    channel: Mapped[str] = mapped_column(String(50), default="in_app")
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
