"""Seed one account per RBAC role. Idempotent (skips existing emails). The shared password
is a development default only and must be rotated before any real deployment.
"""

import asyncio

from app.database.session import AsyncSessionLocal, engine
from app.security.roles import Role
from app.services import users as user_service

DEV_PASSWORD = "Passw0rd!"

USERS = [
    ("admin@construction-ops.com", "System Administrator", Role.ADMIN),
    ("executive@construction-ops.com", "Executive Director", Role.EXECUTIVE),
    ("pm@construction-ops.com", "Project Manager", Role.PROJECT_MANAGER),
    ("engineer@construction-ops.com", "Site Engineer", Role.SITE_ENGINEER),
    ("procurement@construction-ops.com", "Procurement Officer", Role.PROCUREMENT_OFFICER),
    ("qaqc@construction-ops.com", "QA/QC Manager", Role.QA_QC),
    ("viewer@construction-ops.com", "Read-Only User", Role.VIEWER),
]


async def run() -> None:
    created = 0
    async with AsyncSessionLocal() as db:
        for email, full_name, role in USERS:
            if await user_service.get_user_by_email(db, email):
                continue
            await user_service.create_user(
                db, email=email, full_name=full_name, role=role.value, password=DEV_PASSWORD
            )
            created += 1
        await db.commit()

    print(f"users ensured: {len(USERS)}, newly created: {created}")
    print(f"dev password for all seeded accounts: {DEV_PASSWORD}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
