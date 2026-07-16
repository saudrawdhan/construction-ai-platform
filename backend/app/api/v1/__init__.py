from fastapi import APIRouter

from app.api.v1 import (
    ai_agent,
    ai_copilot,
    approvals,
    audit,
    auth,
    change_orders,
    claims,
    documents,
    meetings,
    memory,
    notifications,
    procurement,
    projects,
    reports,
    rfis,
    site_reports,
    suppliers,
    users,
)
from app.config import get_settings

api_router = APIRouter(prefix=get_settings().api_v1_prefix)

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(suppliers.router)
api_router.include_router(procurement.router)
api_router.include_router(rfis.router)
api_router.include_router(change_orders.router)
api_router.include_router(claims.router)
api_router.include_router(meetings.router)
api_router.include_router(site_reports.router)
api_router.include_router(documents.router)
api_router.include_router(reports.router)
api_router.include_router(memory.router)
api_router.include_router(ai_copilot.router)
api_router.include_router(ai_agent.router)
api_router.include_router(approvals.router)
api_router.include_router(audit.router)
api_router.include_router(notifications.router)
