"""Governance service: human-in-the-loop approvals + notifications + AI audit trail.

High-risk actions (external emails, purchase-request approvals, contractual changes) are never
executed by an agent directly — they are recorded as approval_requests and only proceed after a
human approves. Every decision is written to approval_history and notifies the requester.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiAuditLog, ApprovalHistory, ApprovalRequest, Notification
from app.services.users import get_user_by_email


async def request_approval(
    db: AsyncSession,
    *,
    action_type: str,
    project_id: int | None,
    payload: dict | None,
    risk_level: str,
    requested_by: str,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        action_type=action_type,
        project_id=project_id,
        payload=payload,
        risk_level=risk_level,
        requested_by=requested_by,
        status="pending",
    )
    db.add(approval)
    await db.flush()
    db.add(
        ApprovalHistory(
            approval_request_id=approval.id, actor=requested_by, action="requested", note=None
        )
    )
    return approval


async def list_approvals(
    db: AsyncSession, *, page: int, size: int, status: str | None = None,
    risk_level: str | None = None,
) -> tuple[list[ApprovalRequest], int]:
    query = select(ApprovalRequest)
    if status:
        query = query.where(ApprovalRequest.status == status)
    if risk_level:
        query = query.where(ApprovalRequest.risk_level == risk_level)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(ApprovalRequest.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_approval(db: AsyncSession, approval_id: int) -> ApprovalRequest | None:
    return await db.get(ApprovalRequest, approval_id)


async def get_history(db: AsyncSession, approval_id: int) -> list[ApprovalHistory]:
    rows = await db.scalars(
        select(ApprovalHistory)
        .where(ApprovalHistory.approval_request_id == approval_id)
        .order_by(ApprovalHistory.id)
    )
    return list(rows)


async def resolve_approval(
    db: AsyncSession, approval: ApprovalRequest, *, decision: str, actor: str, note: str | None
) -> ApprovalRequest:
    approval.status = decision
    approval.resolved_by = actor
    approval.resolved_at = datetime.now(UTC)
    db.add(
        ApprovalHistory(
            approval_request_id=approval.id, actor=actor, action=decision, note=note
        )
    )
    requester = await get_user_by_email(db, approval.requested_by)
    db.add(
        Notification(
            user_id=requester.id if requester else None,
            project_id=approval.project_id,
            channel="in_app",
            title=f"Approval {decision}",
            body=f"Action '{approval.action_type}' was {decision} by {actor}.",
            category="approval",
        )
    )
    return approval


async def list_notifications(
    db: AsyncSession, *, user_id: int, page: int, size: int, unread_only: bool = False
) -> tuple[list[Notification], int]:
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Notification.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def mark_notification_read(
    db: AsyncSession, *, notification_id: int, user_id: int
) -> Notification | None:
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        return None
    notification.is_read = True
    return notification


async def list_ai_audit(
    db: AsyncSession, *, page: int, size: int, workflow: str | None = None
) -> tuple[list[AiAuditLog], int]:
    query = select(AiAuditLog)
    if workflow:
        query = query.where(AiAuditLog.workflow == workflow)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(AiAuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)
