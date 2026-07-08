from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.governance import AuditLogRead
from app.security.deps import require_roles
from app.security.roles import Role
from app.services import governance as governance_service

router = APIRouter(prefix="/audit", tags=["audit"])

AuditViewers = Annotated[User, Depends(require_roles(Role.ADMIN, Role.EXECUTIVE))]


@router.get("/ai-outputs", response_model=Page[AuditLogRead])
async def list_ai_outputs(
    db: DbSession,
    _: AuditViewers,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    workflow: str | None = None,
) -> Page[AuditLogRead]:
    items, total = await governance_service.list_ai_audit(
        db, page=page, size=size, workflow=workflow
    )
    return Page.build([AuditLogRead.model_validate(a) for a in items], total, page, size)
