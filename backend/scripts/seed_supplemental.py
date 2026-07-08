"""Deterministic seeder for records the source dataset does not contain but the platform
workflows require: RFIs (with a realistic overdue backlog relative to the current date) and
a planned-activity baseline per project (for planned-vs-actual site analysis).

Seeded with a fixed RNG so every run reproduces the same demo data.
"""

import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import func, select, text

from app.database.session import AsyncSessionLocal, engine
from app.models import PlannedActivity, Project, Rfi

RNG = random.Random(42)
TODAY = date(2026, 7, 6)

DISCIPLINES = ["Civil", "Structural", "MEP", "Architectural", "Finishes", "Facade"]
RAISED_BY = ["Site Engineer", "QA/QC Manager", "Construction Manager", "MEP Coordinator"]
ASSIGNED_TO = ["Consultant Engineer", "Design Team", "Client Representative"]
PRIORITIES = ["Low", "Medium", "High"]

SUBJECTS = {
    "Civil": "Clarification on foundation rebar detailing",
    "Structural": "Discrepancy between structural drawings and site condition",
    "MEP": "Coordination clash between ductwork and cable trays",
    "Architectural": "Confirmation of finishing schedule and material spec",
    "Finishes": "Approval request for alternative floor finish",
    "Facade": "Cladding fixing detail at parapet level",
}

BASELINE_ACTIVITIES = [
    ("Site Mobilization", 0.00, 0.08, 20),
    ("Earthworks", 0.05, 0.20, 45),
    ("Civil Works", 0.15, 0.45, 80),
    ("Structural", 0.30, 0.60, 90),
    ("MEP First Fix", 0.45, 0.70, 60),
    ("Facade", 0.55, 0.80, 40),
    ("Finishing", 0.70, 0.95, 70),
    ("Inspection & Handover", 0.90, 1.00, 25),
]


def _fraction_date(start: date, finish: date, fraction: float) -> date:
    span = (finish - start).days
    return start + timedelta(days=int(span * fraction))


def build_rfis(projects: list[Project]) -> list[dict]:
    rfis: list[dict] = []
    for project in projects:
        start = project.start_date or date(2023, 1, 1)
        finish = project.planned_finish or (start + timedelta(days=540))
        window_end = min(finish, TODAY)
        count = RNG.randint(3, 7)
        for index in range(1, count + 1):
            discipline = RNG.choice(DISCIPLINES)
            span = max((window_end - start).days, 30)
            raised = start + timedelta(days=RNG.randint(10, span))
            required = raised + timedelta(days=RNG.choice([7, 10, 14, 21]))
            answered = RNG.random() < 0.45
            response = raised + timedelta(days=RNG.randint(3, 25)) if answered else None
            status = "Closed" if answered else "Open"
            rfis.append(
                {
                    "project_id": project.id,
                    "rfi_number": f"RFI-{project.id:04d}-{index:03d}",
                    "subject": SUBJECTS[discipline],
                    "question": (
                        f"{SUBJECTS[discipline]}. Please review and advise so that the "
                        f"affected {discipline.lower()} activity can proceed without delay."
                    ),
                    "discipline": discipline,
                    "raised_by": RNG.choice(RAISED_BY),
                    "assigned_to": RNG.choice(ASSIGNED_TO),
                    "raised_date": raised,
                    "required_date": required,
                    "response_date": response,
                    "status": status,
                    "priority": RNG.choices(PRIORITIES, weights=[3, 5, 2])[0],
                }
            )
    return rfis


def build_planned_activities(projects: list[Project]) -> list[dict]:
    planned: list[dict] = []
    for project in projects:
        start = project.start_date or date(2023, 1, 1)
        finish = project.planned_finish or (start + timedelta(days=540))
        for sequence, (name, begin, end, manpower) in enumerate(BASELINE_ACTIVITIES, start=1):
            planned.append(
                {
                    "project_id": project.id,
                    "activity_category": name,
                    "planned_start": _fraction_date(start, finish, begin),
                    "planned_finish": _fraction_date(start, finish, end),
                    "planned_manpower": manpower,
                    "sequence": sequence,
                }
            )
    return planned


async def run() -> None:
    async with AsyncSessionLocal() as session:
        projects = list((await session.scalars(select(Project))).all())

        await session.execute(text("TRUNCATE rfis, planned_activities RESTART IDENTITY"))
        await session.execute(Rfi.__table__.insert(), build_rfis(projects))
        await session.execute(
            PlannedActivity.__table__.insert(), build_planned_activities(projects)
        )
        await session.commit()

        rfi_count = await session.scalar(select(func.count()).select_from(Rfi))
        planned_count = await session.scalar(select(func.count()).select_from(PlannedActivity))
        overdue = await session.scalar(
            select(func.count()).select_from(Rfi).where(
                Rfi.status != "Closed", Rfi.required_date < TODAY
            )
        )

    print(f"projects seeded against : {len(projects)}")
    print(f"rfis created            : {rfi_count}")
    print(f"  of which overdue+open : {overdue}")
    print(f"planned_activities      : {planned_count}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
