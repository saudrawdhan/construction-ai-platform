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

from app.agents.workflows import site_report as site_report_workflow
from app.api.deps import DbSession
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.schemas.site_reports import (
    DailyActivityRead,
    SiteReportCreate,
    SiteReportRead,
    SiteReportUpdate,
)
from app.schemas.workflows import SiteReportAnalysis, SiteReportAnalyzeRequest
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import imports as imports_service
from app.services import site_reports as site_report_service
from app.services.llm import get_llm

router = APIRouter(prefix="/site-reports", tags=["site-reports"])

SiteRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER, Role.SITE_ENGINEER))
]

SITE_REPORT_TEMPLATE = (
    "project_code,weather,summary,report_date\n"
    "PRJ-0100,Clear,Concrete pour completed on level 3; no safety incidents,2026-02-05\n"
)


@router.post("", response_model=SiteReportRead, status_code=status.HTTP_201_CREATED)
async def create_site_report(
    payload: SiteReportCreate, db: DbSession, _: SiteRoles
) -> SiteReportRead:
    report = await site_report_service.create_site_report(db, payload)
    await db.commit()
    await db.refresh(report)
    return SiteReportRead.model_validate(report)


@router.get("/import/template")
async def site_report_import_template(_: SiteRoles) -> Response:
    return Response(
        content=SITE_REPORT_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=site_reports_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_site_reports(
    db: DbSession,
    _: SiteRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.project_code_resolver(db)
    return await handle_tabular_import(
        db,
        file,
        dry_run,
        schema=SiteReportCreate,
        create=site_report_service.create_site_report,
        resolve=resolve,
    )


@router.post("/{project_id}/analyze", response_model=SiteReportAnalysis)
async def analyze_site_report(
    project_id: int, payload: SiteReportAnalyzeRequest, db: DbSession, _: SiteRoles
) -> SiteReportAnalysis:
    result = await site_report_workflow.run(
        db, project_id=project_id, payload=payload, llm=get_llm()
    )
    await db.commit()
    return result


@router.get("", response_model=Page[SiteReportRead])
async def list_site_reports(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
) -> Page[SiteReportRead]:
    items, total = await site_report_service.list_site_reports(
        db, page=page, size=size, project_id=project_id
    )
    return Page.build([SiteReportRead.model_validate(r) for r in items], total, page, size)


@router.get("/{report_id}", response_model=SiteReportRead)
async def get_site_report(
    report_id: int, db: DbSession, _: CurrentUser
) -> SiteReportRead:
    report = await site_report_service.get_site_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site report not found")
    return SiteReportRead.model_validate(report)


@router.patch("/{report_id}", response_model=SiteReportRead)
async def update_site_report(
    report_id: int, payload: SiteReportUpdate, db: DbSession, _: SiteRoles
) -> SiteReportRead:
    report = await site_report_service.update_site_report(db, report_id, payload)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site report not found")
    await db.commit()
    await db.refresh(report)
    return SiteReportRead.model_validate(report)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_report(report_id: int, db: DbSession, _: SiteRoles) -> None:
    if not await site_report_service.delete_site_report(db, report_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site report not found")
    await db.commit()


@router.get("/{report_id}/activities", response_model=list[DailyActivityRead])
async def list_activities(
    report_id: int, db: DbSession, _: CurrentUser
) -> list[DailyActivityRead]:
    if await site_report_service.get_site_report(db, report_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site report not found")
    activities = await site_report_service.list_activities(db, report_id)
    return [DailyActivityRead.model_validate(a) for a in activities]
