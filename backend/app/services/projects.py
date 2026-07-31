from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Client,
    Project,
    ProjectDecision,
    ProjectIssue,
    ProjectMilestone,
    ProjectRisk,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectIssueCreate,
    ProjectMilestoneCreate,
    ProjectRiskCreate,
    ProjectUpdate,
)


async def list_projects(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    status: str | None = None,
    city: str | None = None,
    project_type: str | None = None,
) -> tuple[list[Project], int]:
    query = select(Project)
    if status:
        query = query.where(Project.status == status)
    if city:
        query = query.where(Project.city == city)
    if project_type:
        query = query.where(Project.project_type == project_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Project.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_project(db: AsyncSession, project_id: int) -> Project | None:
    return await db.get(Project, project_id)


async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
    client = await db.scalar(select(Client).where(Client.name == data.client_name))
    if client is None:
        client = Client(name=data.client_name)
        db.add(client)
        await db.flush()

    project = Project(**data.model_dump(), client_id=client.id)
    db.add(project)
    await db.flush()
    return project


async def update_project(
    db: AsyncSession, project_id: int, data: ProjectUpdate
) -> Project | None:
    project = await db.get(Project, project_id)
    if project is None:
        return None
    fields = data.model_dump(exclude_unset=True)
    if "client_name" in fields:
        client = await db.scalar(select(Client).where(Client.name == fields["client_name"]))
        if client is None:
            client = Client(name=fields["client_name"])
            db.add(client)
            await db.flush()
        project.client_id = client.id
    for field, value in fields.items():
        setattr(project, field, value)
    await db.flush()
    return project


async def delete_project(db: AsyncSession, project_id: int) -> bool:
    project = await db.get(Project, project_id)
    if project is None:
        return False
    await db.delete(project)
    await db.flush()
    return True


async def list_risks(db: AsyncSession, project_id: int) -> list[ProjectRisk]:
    rows = await db.scalars(
        select(ProjectRisk)
        .where(ProjectRisk.project_id == project_id)
        .order_by(ProjectRisk.id)
    )
    return list(rows)


async def create_risk(
    db: AsyncSession, project_id: int, data: ProjectRiskCreate
) -> ProjectRisk:
    risk = ProjectRisk(project_id=project_id, **data.model_dump())
    db.add(risk)
    await db.flush()
    return risk


async def list_issues(db: AsyncSession, project_id: int) -> list[ProjectIssue]:
    rows = await db.scalars(
        select(ProjectIssue)
        .where(ProjectIssue.project_id == project_id)
        .order_by(ProjectIssue.id)
    )
    return list(rows)


async def create_issue(
    db: AsyncSession, project_id: int, data: ProjectIssueCreate
) -> ProjectIssue:
    issue = ProjectIssue(project_id=project_id, **data.model_dump())
    db.add(issue)
    await db.flush()
    return issue


async def list_milestones(db: AsyncSession, project_id: int) -> list[ProjectMilestone]:
    # Ordered by the date the milestone is aimed at rather than insertion order, since a
    # programme is read chronologically; undated entries sort last instead of leading.
    rows = await db.scalars(
        select(ProjectMilestone)
        .where(ProjectMilestone.project_id == project_id)
        .order_by(
            ProjectMilestone.planned_date.is_(None),
            ProjectMilestone.planned_date,
            ProjectMilestone.id,
        )
    )
    return list(rows)


async def create_milestone(
    db: AsyncSession, project_id: int, data: ProjectMilestoneCreate
) -> ProjectMilestone:
    milestone = ProjectMilestone(project_id=project_id, **data.model_dump())
    db.add(milestone)
    await db.flush()
    return milestone


async def list_decisions(db: AsyncSession, project_id: int) -> list[ProjectDecision]:
    """Every decision recorded across the project's meetings, newest first — the meetings API
    exposes these only one meeting at a time, which leaves no way to read a project's decision
    history as a whole."""
    rows = await db.scalars(
        select(ProjectDecision)
        .where(ProjectDecision.project_id == project_id)
        .order_by(
            ProjectDecision.decision_date.is_(None),
            ProjectDecision.decision_date.desc(),
            ProjectDecision.id.desc(),
        )
    )
    return list(rows)
