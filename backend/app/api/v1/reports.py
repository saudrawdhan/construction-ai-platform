from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.workflows import executive_report
from app.api.deps import DbSession
from app.models import User
from app.schemas.workflows import ExecutiveReport, ExecutiveReportRequest
from app.security.deps import require_roles
from app.security.roles import Role
from app.services.llm import get_llm

router = APIRouter(prefix="/reports", tags=["reports"])

ReportRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER))
]


@router.post("/executive-weekly", response_model=ExecutiveReport)
async def executive_weekly_report(
    payload: ExecutiveReportRequest, db: DbSession, _: ReportRoles
) -> ExecutiveReport:
    result = await executive_report.run(db, payload=payload, llm=get_llm())
    await db.commit()
    return result
