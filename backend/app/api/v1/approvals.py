from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.governance import (
    ApprovalCreate,
    ApprovalDecision,
    ApprovalHistoryRead,
    ApprovalRead,
)
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import governance as governance_service

router = APIRouter(prefix="/approvals", tags=["approvals"])

Requesters = Annotated[
    User,
    Depends(
        require_roles(
            Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER, Role.SITE_ENGINEER,
            Role.PROCUREMENT_OFFICER, Role.QA_QC,
        )
    ),
]
Approvers = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER))
]


@router.post("", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: ApprovalCreate, db: DbSession, user: Requesters
) -> ApprovalRead:
    approval = await governance_service.request_approval(
        db,
        action_type=payload.action_type,
        project_id=payload.project_id,
        payload=payload.payload,
        risk_level=payload.risk_level,
        requested_by=user.email,
    )
    await db.commit()
    await db.refresh(approval)
    return ApprovalRead.model_validate(approval)


@router.get("", response_model=Page[ApprovalRead])
async def list_approvals(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    risk_level: str | None = None,
) -> Page[ApprovalRead]:
    items, total = await governance_service.list_approvals(
        db, page=page, size=size, status=status, risk_level=risk_level
    )
    return Page.build([ApprovalRead.model_validate(a) for a in items], total, page, size)


@router.get("/{approval_id}", response_model=ApprovalRead)
async def get_approval(approval_id: int, db: DbSession, _: CurrentUser) -> ApprovalRead:
    approval = await governance_service.get_approval(db, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return ApprovalRead.model_validate(approval)


@router.get("/{approval_id}/history", response_model=list[ApprovalHistoryRead])
async def get_history(
    approval_id: int, db: DbSession, _: CurrentUser
) -> list[ApprovalHistoryRead]:
    if await governance_service.get_approval(db, approval_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    history = await governance_service.get_history(db, approval_id)
    return [ApprovalHistoryRead.model_validate(h) for h in history]


async def _resolve(
    approval_id: int, decision: str, note: str | None, db: DbSession, user: User
) -> ApprovalRead:
    approval = await governance_service.get_approval(db, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    if approval.status != "pending":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Already {approval.status}"
        )
    resolved = await governance_service.resolve_approval(
        db, approval, decision=decision, actor=user.email, note=note
    )
    if not resolved:
        # Lost a concurrent race: another approver flipped this request between the check above
        # and the atomic UPDATE. Report the resolution that actually won.
        await db.refresh(approval)
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Already {approval.status}"
        )
    await db.commit()
    await db.refresh(approval)
    return ApprovalRead.model_validate(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalRead)
async def approve(
    approval_id: int, db: DbSession, user: Approvers, payload: ApprovalDecision | None = None
) -> ApprovalRead:
    return await _resolve(approval_id, "approved", payload.note if payload else None, db, user)


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
async def reject(
    approval_id: int, db: DbSession, user: Approvers, payload: ApprovalDecision | None = None
) -> ApprovalRead:
    return await _resolve(approval_id, "rejected", payload.note if payload else None, db, user)
