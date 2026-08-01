"""Governance service: human-in-the-loop approvals + notifications + AI audit trail.

High-risk actions (external emails, purchase-request approvals, contractual changes) are never
executed by an agent directly — they are recorded as approval_requests and only proceed after a
human approves. Every decision is written to approval_history and notifies the requester.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AiAuditLog,
    ApprovalHistory,
    ApprovalRequest,
    Notification,
    PurchaseRequest,
    User,
)
from app.security.roles import Role
from app.services.users import get_user_by_email

# Mirrors the role gate on POST /approvals/{id}/approve — the people who will actually have to act
# on the request are the people told it exists.
_APPROVER_ROLES = (Role.ADMIN.value, Role.EXECUTIVE.value, Role.PROJECT_MANAGER.value)


async def _notify_approvers(db: AsyncSession, approval: ApprovalRequest) -> None:
    """Tell the approvers a request is waiting for them.

    Only the requester was ever notified, and only after a decision had been made — so nothing
    told an approver that a request existed in the first place. A high-risk action could sit
    pending indefinitely because the one person able to release it never learned of it.
    """
    approvers = await db.scalars(
        select(User).where(User.role.in_(_APPROVER_ROLES), User.is_active.is_(True))
    )
    for approver in approvers:
        db.add(
            Notification(
                user_id=approver.id,
                project_id=approval.project_id,
                channel="in_app",
                title="Approval requested",
                body=(
                    f"{approval.requested_by} requested approval for "
                    f"'{approval.action_type}' ({approval.risk_level} risk)."
                ),
                category="approval",
            )
        )


async def request_approval(
    db: AsyncSession,
    *,
    action_type: str,
    project_id: int | None,
    payload: dict | None,
    risk_level: str,
    requested_by: str,
    subject_type: str | None = None,
    subject_id: int | None = None,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        action_type=action_type,
        project_id=project_id,
        payload=payload,
        risk_level=risk_level,
        requested_by=requested_by,
        status="pending",
        subject_type=subject_type,
        subject_id=subject_id,
    )
    db.add(approval)
    await db.flush()
    db.add(
        ApprovalHistory(
            approval_request_id=approval.id, actor=requested_by, action="requested", note=None
        )
    )
    await _notify_approvers(db, approval)
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


# What each kind of subject becomes once its approval is decided. Only records with a real,
# unambiguous next state appear here — an approval whose subject has no defined transition (an
# advisory recommendation, for instance) is still recorded, it simply moves nothing. Statuses are
# the vocabulary already present in the data, not a new one invented for this table.
_SUBJECT_TRANSITIONS: dict[str, tuple[type, dict[str, str]]] = {
    "purchase_request": (
        PurchaseRequest,
        {"approved": "Approved", "rejected": "Returned to Requester"},
    ),
}


async def apply_subject_transition(
    db: AsyncSession, approval: ApprovalRequest, decision: str
) -> str | None:
    """Move the approved record to the state the decision implies, returning that state.

    Returns None when the approval names no subject, the subject type has no defined transition,
    or the record has since been deleted — all ordinary cases, not failures: the verdict itself is
    already recorded either way, so a missing subject must never fail the approval.
    """
    entry = _SUBJECT_TRANSITIONS.get(approval.subject_type or "")
    if entry is None or approval.subject_id is None:
        return None
    model, outcomes = entry
    new_status = outcomes.get(decision)
    if new_status is None:
        return None
    subject = await db.get(model, approval.subject_id)
    if subject is None:
        return None
    subject.status = new_status
    await db.flush()
    return new_status


async def resolve_approval(
    db: AsyncSession, approval: ApprovalRequest, *, decision: str, actor: str, note: str | None
) -> bool:
    """Atomically move a pending approval to its decision and record the history + notification.

    The pending -> decided transition is a single conditional UPDATE (``WHERE status = 'pending'``)
    rather than a read-check-write on the ORM object: a router-level ``if status != "pending"``
    check has a time-of-check/time-of-use gap under which two concurrent approvers could both pass
    the check and both resolve the same request. The UPDATE's row count is the authority — exactly
    one caller can flip a pending row, so only that caller writes the history entry and notifies the
    requester. Returns True if this call performed the transition, False if it lost the race (the
    row was no longer pending) — the caller maps False to a 409.
    """
    resolved_at = datetime.now(UTC)
    result = await db.execute(
        update(ApprovalRequest)
        .where(ApprovalRequest.id == approval.id, ApprovalRequest.status == "pending")
        .values(status=decision, resolved_by=actor, resolved_at=resolved_at)
    )
    if result.rowcount == 0:
        return False
    # The UPDATE above is the only write to the approval row; the caller refreshes the instance
    # after commit to pick up the new state, so it is deliberately not mutated here (mutating it
    # would make the ORM flush a second, redundant UPDATE of the same values).
    db.add(
        ApprovalHistory(
            approval_request_id=approval.id, actor=actor, action=decision, note=note
        )
    )
    # Only the caller that actually won the pending -> decided race reaches here, so the subject
    # can never be transitioned twice by two concurrent approvers.
    await apply_subject_transition(db, approval, decision)
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
    return True


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
