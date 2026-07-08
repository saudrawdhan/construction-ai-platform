from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.schemas.commercial import ChangeOrderRead
from app.schemas.common import Page
from app.security.deps import CurrentUser
from app.services import commercial as commercial_service

router = APIRouter(prefix="/change-orders", tags=["change-orders"])


@router.get("", response_model=Page[ChangeOrderRead])
async def list_change_orders(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    status: str | None = None,
) -> Page[ChangeOrderRead]:
    items, total = await commercial_service.list_change_orders(
        db, page=page, size=size, project_id=project_id, status=status
    )
    return Page.build([ChangeOrderRead.model_validate(c) for c in items], total, page, size)


@router.get("/{co_id}", response_model=ChangeOrderRead)
async def get_change_order(co_id: int, db: DbSession, _: CurrentUser) -> ChangeOrderRead:
    change_order = await commercial_service.get_change_order(db, co_id)
    if change_order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Change order not found")
    return ChangeOrderRead.model_validate(change_order)
