from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meeting, MeetingActionItem, ProjectDecision
from app.schemas.meetings import MeetingCreate, MeetingUpdate


async def create_meeting(db: AsyncSession, payload: MeetingCreate) -> Meeting:
    meeting = Meeting(**payload.model_dump())
    db.add(meeting)
    await db.flush()
    return meeting


async def update_meeting(
    db: AsyncSession, meeting_id: int, payload: MeetingUpdate
) -> Meeting | None:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(meeting, field, value)
    await db.flush()
    return meeting


async def delete_meeting(db: AsyncSession, meeting_id: int) -> bool:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        return False
    await db.delete(meeting)
    await db.flush()
    return True


async def list_meetings(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    meeting_type: str | None = None,
) -> tuple[list[Meeting], int]:
    query = select(Meeting)
    if project_id:
        query = query.where(Meeting.project_id == project_id)
    if meeting_type:
        query = query.where(Meeting.meeting_type == meeting_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Meeting.meeting_date.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_meeting(db: AsyncSession, meeting_id: int) -> Meeting | None:
    return await db.get(Meeting, meeting_id)


async def list_action_items(db: AsyncSession, meeting_id: int) -> list[MeetingActionItem]:
    rows = await db.scalars(
        select(MeetingActionItem)
        .where(MeetingActionItem.meeting_id == meeting_id)
        .order_by(MeetingActionItem.id)
    )
    return list(rows)


async def list_decisions(db: AsyncSession, meeting_id: int) -> list[ProjectDecision]:
    rows = await db.scalars(
        select(ProjectDecision)
        .where(ProjectDecision.meeting_id == meeting_id)
        .order_by(ProjectDecision.id)
    )
    return list(rows)
