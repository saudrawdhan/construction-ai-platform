"""Run every scheduled automation once and print its result — a dry run (rolls back, no
persistence) so it can be demoed without polluting the database. The arq worker runs the same
task logic on a cron schedule and commits.
"""

import asyncio

from app.database.session import AsyncSessionLocal, engine
from app.services.llm import get_llm
from app.worker import tasks


async def run() -> None:
    async with AsyncSessionLocal() as db:
        print("daily_site_summary   :", await tasks.daily_site_summary(db))
        print("overdue_rfi_reminder :", await tasks.overdue_rfi_reminder(db))
        print("pending_pr_alert     :", await tasks.pending_pr_alert(db))
        print("weekly_exec_report   :", await tasks.weekly_executive_report(db, get_llm()))
        await db.rollback()  # dry run — do not persist
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
