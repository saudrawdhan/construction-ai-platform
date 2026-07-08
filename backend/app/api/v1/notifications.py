from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.schemas.common import Page
from app.schemas.governance import NotificationRead
from app.security.deps import CurrentUser
from app.services import governance as governance_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationRead])
async def list_notifications(
    db: DbSession,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    unread_only: bool = False,
) -> Page[NotificationRead]:
    items, total = await governance_service.list_notifications(
        db, user_id=user.id, page=page, size=size, unread_only=unread_only
    )
    return Page.build([NotificationRead.model_validate(n) for n in items], total, page, size)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int, db: DbSession, user: CurrentUser
) -> NotificationRead:
    notification = await governance_service.mark_notification_read(
        db, notification_id=notification_id, user_id=user.id
    )
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()
    await db.refresh(notification)
    return NotificationRead.model_validate(notification)
