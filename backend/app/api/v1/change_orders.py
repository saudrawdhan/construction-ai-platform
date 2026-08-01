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

from app.api.deps import DbSession
from app.api.v1.import_helpers import handle_tabular_import
from app.models import Project, User
from app.schemas.commercial import (
    ChangeOrderCreate,
    ChangeOrderImpact,
    ChangeOrderRead,
    ChangeOrderUpdate,
)
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import commercial as commercial_service
from app.services import imports as imports_service

router = APIRouter(prefix="/change-orders", tags=["change-orders"])

ManageRoles = Annotated[User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER))]

CHANGE_ORDER_TEMPLATE = (
    "project_code,co_number,description,value,status\n"
    "PRJ-0100,CO-001,Added scope for extra formwork to level 3,125000,Pending\n"
)


@router.post("", response_model=ChangeOrderRead, status_code=status.HTTP_201_CREATED)
async def create_change_order(
    payload: ChangeOrderCreate, db: DbSession, _: ManageRoles
) -> ChangeOrderRead:
    change_order = await commercial_service.create_change_order(db, payload)
    await db.commit()
    await db.refresh(change_order)
    return ChangeOrderRead.model_validate(change_order)


@router.get("/import/template")
async def change_order_import_template(_: ManageRoles) -> Response:
    return Response(
        content=CHANGE_ORDER_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=change_orders_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_change_orders(
    db: DbSession,
    _: ManageRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.project_code_resolver(db)
    return await handle_tabular_import(
        db,
        file,
        dry_run,
        schema=ChangeOrderCreate,
        create=commercial_service.create_change_order,
        resolve=resolve,
    )


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


@router.get("/impact/{project_id}", response_model=ChangeOrderImpact)
async def project_change_order_impact(
    project_id: int, db: DbSession, _: CurrentUser
) -> ChangeOrderImpact:
    """Cost, programme and cause roll-up for one project's change orders."""
    # Without this an unknown project returns a roll-up of zeros, which reads as "this project has
    # no change orders" rather than "there is no such project" — the sibling project endpoints all
    # answer 404, and a zeroed commercial position is the more dangerous of the two to believe.
    if await db.get(Project, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await commercial_service.change_order_impact(db, project_id)


@router.get("/{co_id}", response_model=ChangeOrderRead)
async def get_change_order(co_id: int, db: DbSession, _: CurrentUser) -> ChangeOrderRead:
    change_order = await commercial_service.get_change_order(db, co_id)
    if change_order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Change order not found")
    return ChangeOrderRead.model_validate(change_order)


@router.patch("/{co_id}", response_model=ChangeOrderRead)
async def update_change_order(
    co_id: int, payload: ChangeOrderUpdate, db: DbSession, _: ManageRoles
) -> ChangeOrderRead:
    change_order = await commercial_service.update_change_order(db, co_id, payload)
    if change_order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Change order not found")
    await db.commit()
    await db.refresh(change_order)
    return ChangeOrderRead.model_validate(change_order)


@router.delete("/{co_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_change_order(co_id: int, db: DbSession, _: ManageRoles) -> None:
    if not await commercial_service.delete_change_order(db, co_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Change order not found")
    await db.commit()
