from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.agents.workflows import rfi_escalation
from app.api.deps import DbSession, RequestLanguage
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.schemas.technical import RfiCreate, RfiRead, RfiUpdate
from app.schemas.workflows import RfiEscalation
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import imports as imports_service
from app.services import technical as technical_service
from app.services.llm import get_llm

router = APIRouter(prefix="/rfis", tags=["rfis"])

RfiRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER, Role.SITE_ENGINEER))
]

RFI_TEMPLATE = (
    "project_code,rfi_number,subject,question,discipline,raised_by,assigned_to,"
    "raised_date,required_date,priority\n"
    "PRJ-0100,RFI-001,Rebar spacing at grid B3,Please confirm rebar spacing at grid B3,"
    "Structural,Site Engineer,Design Lead,2026-02-01,2026-02-10,High\n"
)


@router.post("", response_model=RfiRead, status_code=status.HTTP_201_CREATED)
async def create_rfi(payload: RfiCreate, db: DbSession, _: RfiRoles) -> RfiRead:
    rfi = await technical_service.create_rfi(db, payload)
    await db.commit()
    await db.refresh(rfi)
    return RfiRead.model_validate(rfi)


@router.get("/import/template")
async def rfi_import_template(_: RfiRoles) -> Response:
    return Response(
        content=RFI_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rfis_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_rfis(
    db: DbSession,
    _: RfiRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.project_code_resolver(db)
    return await handle_tabular_import(
        db, file, dry_run, schema=RfiCreate, create=technical_service.create_rfi, resolve=resolve
    )


@router.post("/{project_id}/analyze", response_model=RfiEscalation)
async def analyze_project_rfis(
    project_id: int, db: DbSession, _: RfiRoles, language: RequestLanguage
) -> RfiEscalation:
    result = await rfi_escalation.run(
        db, project_id=project_id, llm=get_llm(), language=language
    )
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


@router.patch("/{rfi_id}", response_model=RfiRead)
async def update_rfi(
    rfi_id: int, payload: RfiUpdate, db: DbSession, _: RfiRoles
) -> RfiRead:
    rfi = await technical_service.update_rfi(db, rfi_id, payload)
    if rfi is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RFI not found")
    await db.commit()
    await db.refresh(rfi)
    return RfiRead.model_validate(rfi)


@router.delete("/{rfi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rfi(rfi_id: int, db: DbSession, _: RfiRoles) -> None:
    if not await technical_service.delete_rfi(db, rfi_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="RFI not found")
    await db.commit()
