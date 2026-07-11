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

from app.agents.workflows import meeting_summary
from app.api.deps import DbSession
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.schemas.meetings import (
    MeetingActionItemRead,
    MeetingCreate,
    MeetingDecisionRead,
    MeetingRead,
    MeetingUpdate,
)
from app.schemas.workflows import MeetingSummarizeRequest, MeetingSummary
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import imports as imports_service
from app.services import meetings as meeting_service
from app.services.llm import get_llm

router = APIRouter(prefix="/meetings", tags=["meetings"])

MeetingRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER, Role.QA_QC))
]

MEETING_TEMPLATE = (
    "project_code,title,meeting_type,meeting_date\n"
    "PRJ-0100,Weekly Progress Meeting,Progress,2026-02-05\n"
)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
async def create_meeting(payload: MeetingCreate, db: DbSession, _: MeetingRoles) -> MeetingRead:
    meeting = await meeting_service.create_meeting(db, payload)
    await db.commit()
    await db.refresh(meeting)
    return MeetingRead.model_validate(meeting)


@router.get("/import/template")
async def meeting_import_template(_: MeetingRoles) -> Response:
    return Response(
        content=MEETING_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=meetings_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_meetings(
    db: DbSession,
    _: MeetingRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.project_code_resolver(db)
    return await handle_tabular_import(
        db,
        file,
        dry_run,
        schema=MeetingCreate,
        create=meeting_service.create_meeting,
        resolve=resolve,
    )


@router.post("/{project_id}/summarize", response_model=MeetingSummary)
async def summarize_meeting(
    project_id: int, payload: MeetingSummarizeRequest, db: DbSession, _: MeetingRoles
) -> MeetingSummary:
    result = await meeting_summary.run(
        db, project_id=project_id, payload=payload, llm=get_llm()
    )
    await db.commit()
    return result


@router.get("", response_model=Page[MeetingRead])
async def list_meetings(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    meeting_type: str | None = None,
) -> Page[MeetingRead]:
    items, total = await meeting_service.list_meetings(
        db, page=page, size=size, project_id=project_id, meeting_type=meeting_type
    )
    return Page.build([MeetingRead.model_validate(m) for m in items], total, page, size)


async def _require_meeting(db: DbSession, meeting_id: int) -> None:
    if await meeting_service.get_meeting(db, meeting_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Meeting not found")


@router.get("/{meeting_id}", response_model=MeetingRead)
async def get_meeting(meeting_id: int, db: DbSession, _: CurrentUser) -> MeetingRead:
    meeting = await meeting_service.get_meeting(db, meeting_id)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return MeetingRead.model_validate(meeting)


@router.patch("/{meeting_id}", response_model=MeetingRead)
async def update_meeting(
    meeting_id: int, payload: MeetingUpdate, db: DbSession, _: MeetingRoles
) -> MeetingRead:
    meeting = await meeting_service.update_meeting(db, meeting_id, payload)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    await db.commit()
    await db.refresh(meeting)
    return MeetingRead.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(meeting_id: int, db: DbSession, _: MeetingRoles) -> None:
    if not await meeting_service.delete_meeting(db, meeting_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    await db.commit()


@router.get("/{meeting_id}/action-items", response_model=list[MeetingActionItemRead])
async def list_action_items(
    meeting_id: int, db: DbSession, _: CurrentUser
) -> list[MeetingActionItemRead]:
    await _require_meeting(db, meeting_id)
    items = await meeting_service.list_action_items(db, meeting_id)
    return [MeetingActionItemRead.model_validate(i) for i in items]


@router.get("/{meeting_id}/decisions", response_model=list[MeetingDecisionRead])
async def list_decisions(
    meeting_id: int, db: DbSession, _: CurrentUser
) -> list[MeetingDecisionRead]:
    await _require_meeting(db, meeting_id)
    decisions = await meeting_service.list_decisions(db, meeting_id)
    return [MeetingDecisionRead.model_validate(d) for d in decisions]
