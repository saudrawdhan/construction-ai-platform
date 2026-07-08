from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Project, ProjectRisk
from app.schemas.project import ProjectCreate, ProjectRiskCreate


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
