from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectRiskCreate,
    ProjectRiskRead,
)
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import projects as project_service

router = APIRouter(prefix="/projects", tags=["projects"])

ProjectManagers = Annotated[User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER))]


@router.get("", response_model=Page[ProjectRead])
async def list_projects(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    city: str | None = None,
    project_type: str | None = None,
) -> Page[ProjectRead]:
    items, total = await project_service.list_projects(
        db, page=page, size=size, status=status, city=city, project_type=project_type
    )
    return Page.build([ProjectRead.model_validate(p) for p in items], total, page, size)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, db: DbSession, _: ProjectManagers
) -> ProjectRead:
    project = await project_service.create_project(db, payload)
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, db: DbSession, _: CurrentUser) -> ProjectRead:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.get("/{project_id}/risks", response_model=list[ProjectRiskRead])
async def list_project_risks(
    project_id: int, db: DbSession, _: CurrentUser
) -> list[ProjectRiskRead]:
    if await project_service.get_project(db, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    risks = await project_service.list_risks(db, project_id)
    return [ProjectRiskRead.model_validate(r) for r in risks]


@router.post(
    "/{project_id}/risks",
    response_model=ProjectRiskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_risk(
    project_id: int, payload: ProjectRiskCreate, db: DbSession, _: ProjectManagers
) -> ProjectRiskRead:
    if await project_service.get_project(db, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    risk = await project_service.create_risk(db, project_id, payload)
    await db.commit()
    await db.refresh(risk)
    return ProjectRiskRead.model_validate(risk)
