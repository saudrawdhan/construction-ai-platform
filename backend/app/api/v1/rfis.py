from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agents.workflows import rfi_escalation
from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.technical import RfiRead
from app.schemas.workflows import RfiEscalation
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import technical as technical_service
from app.services.llm import get_llm

router = APIRouter(prefix="/rfis", tags=["rfis"])

RfiRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER, Role.SITE_ENGINEER))
]


@router.post("/{project_id}/analyze", response_model=RfiEscalation)
async def analyze_project_rfis(
    project_id: int, db: DbSession, _: RfiRoles
) -> RfiEscalation:
    result = await rfi_escalation.run(db, project_id=project_id, llm=get_llm())
    await db.commit()
    return result


@router.get("", response_model=Page[RfiRead])
async def list_rfis(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    status: str | None = None,
    discipline: str | None = None,
    overdue: bool = False,
) -> Page[RfiRead]:
    items, total = await technical_service.list_rfis(
        db,
        page=page,
        size=size,
        project_id=project_id,
        status=status,
        discipline=discipline,
        overdue=overdue,
    )
    return Page.build([RfiRead.model_validate(r) for r in items], total, page, size)


@router.get("/{rfi_id}", response_model=RfiRead)
async def get_rfi(rfi_id: int, db: DbSession, _: CurrentUser) -> RfiRead:
    rfi = await technical_service.get_rfi(db, rfi_id)
    if rfi is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RFI not found")
    return RfiRead.model_validate(rfi)
