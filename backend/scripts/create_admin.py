"""Create the first administrator account on a fresh install.

A new deployment starts with an empty database and no users. This command bootstraps the initial
admin so someone can log in and then manage everything else (users, projects, suppliers, ...) from
the application itself — no seed dataset required.

Reads ADMIN_EMAIL, ADMIN_PASSWORD, and optional ADMIN_NAME from the environment. Idempotent: if the
email already exists it reports that and changes nothing.

    docker compose run --rm \
      -e ADMIN_EMAIL=admin@yourcompany.com \
      -e ADMIN_PASSWORD='ChangeMe!23' \
      -e ADMIN_NAME='Site Admin' \
      api python -m scripts.create_admin
"""

import asyncio
import os

from app.database.session import AsyncSessionLocal, engine
from app.security.roles import Role
from app.services import users as user_service


async def run() -> None:
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    name = os.environ.get("ADMIN_NAME", "Administrator")

    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD to create the first admin account.")
        return

    async with AsyncSessionLocal() as db:
        existing = await user_service.get_user_by_email(db, email)
        if existing is not None:
            print(f"A user with email {email} already exists (role={existing.role}). No change.")
        else:
            await user_service.create_user(
                db, email=email, full_name=name, role=Role.ADMIN.value, password=password
            )
            await db.commit()
            print(f"Created administrator {email}.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
