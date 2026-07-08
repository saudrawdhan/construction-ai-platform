"""arq worker: registers the scheduled automations and their cron schedule. Each job opens an
async session, runs the task logic, and commits. The worker service runs with LLM_PROVIDER=mock
so recurring jobs are deterministic and never spend Gemini quota.
"""

from collections.abc import Awaitable, Callable

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.database.session import AsyncSessionLocal, engine
from app.services.llm import get_llm
from app.worker import tasks

settings = get_settings()


async def _run(func: Callable, *, with_llm: bool = False) -> dict:
    async with AsyncSessionLocal() as db:
        result = await (func(db, get_llm()) if with_llm else func(db))
        await db.commit()
    return result


async def daily_site_summary(ctx: dict) -> dict:
    return await _run(tasks.daily_site_summary)


async def overdue_rfi_reminder(ctx: dict) -> dict:
    return await _run(tasks.overdue_rfi_reminder)


async def pending_pr_alert(ctx: dict) -> dict:
    return await _run(tasks.pending_pr_alert)


async def weekly_executive_report(ctx: dict) -> dict:
    return await _run(tasks.weekly_executive_report, with_llm=True)


async def _shutdown(ctx: dict) -> None:
    await engine.dispose()


_FUNCTIONS: list[Callable[[dict], Awaitable[dict]]] = [
    daily_site_summary,
    overdue_rfi_reminder,
    pending_pr_alert,
    weekly_executive_report,
]


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = _FUNCTIONS
    on_shutdown = _shutdown
    cron_jobs = [
        cron(daily_site_summary, hour=6, minute=0),
        cron(overdue_rfi_reminder, hour=7, minute=0),
        cron(pending_pr_alert, hour=7, minute=30),
        cron(weekly_executive_report, weekday=0, hour=8, minute=0),
    ]
