"""Populate an empty database with a realistic, self-contained demo portfolio.

Purpose: let anyone clone the repository and run a fully populated application WITHOUT the private
source dataset. The data is synthetic but coherent — each project owns its RFIs, meetings, site
reports, change orders, claims, and procurement, with a mix of late and on-time purchase orders — so
every screen and AI workflow has something to show. Generation is deterministic (fixed seed) and the
script refuses to run against a non-empty database unless FORCE_DEMO_SEED=1, so it never doubles up
on existing data.

Run: docker compose run --rm api python -m scripts.seed_demo_data
"""

import asyncio
import os
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal, engine
from app.models import (
    ChangeOrder,
    Claim,
    Client,
    Meeting,
    Project,
    PurchaseOrder,
    PurchaseRequest,
    Rfi,
    SiteReport,
    Supplier,
)
from app.security.roles import Role
from app.services import users as user_service

DEV_PASSWORD = "Passw0rd!"
TODAY = date(2026, 7, 10)

DEMO_USERS = [
    ("admin@construction-ops.com", "Omar Al-Harbi", Role.ADMIN),
    ("executive@construction-ops.com", "Faisal Al-Rashid", Role.EXECUTIVE),
    ("pm@construction-ops.com", "Khalid Al-Otaibi", Role.PROJECT_MANAGER),
    ("engineer@construction-ops.com", "Yousef Ahmed", Role.SITE_ENGINEER),
    ("procurement@construction-ops.com", "Noura Al-Qahtani", Role.PROCUREMENT_OFFICER),
    ("qaqc@construction-ops.com", "Sami Haddad", Role.QA_QC),
    ("viewer@construction-ops.com", "Layla Nasser", Role.VIEWER),
]

CITIES = ["Riyadh", "Jeddah", "Dammam", "Khobar", "Makkah", "Madinah", "Tabuk", "Jubail"]
CLIENTS = [
    "Gulf Energy Holdings",
    "Coastal Development Authority",
    "National Health Directorate",
    "Vision Coastal City",
    "Horizon Residential Group",
    "Capital Design Partners",
]
DISCIPLINES = ["Structural", "Architectural", "MEP", "Civil", "Electrical"]
MATERIALS = ["Steel", "Concrete", "MEP", "Electrical", "Facade", "Finishing"]
MEETING_TYPES = ["Progress Review", "Technical Coordination", "Safety Review", "Client Meeting"]
WEATHER = ["Clear", "Hot", "Dusty", "Humid"]

SUPPLIERS = [
    "Falcon Steel Works", "Desert Readymix", "Meridian Industrial", "Cedar Contracting",
    "Oasis Electric", "Summit MEP", "Pearl Building Supplies", "Lantern Electric",
    "Highland Cement", "Anchor Engineering",
]

PROJECTS = [
    ("Riyadh Commercial Tower", "Tower"),
    ("Central Hospital Extension", "Hospital"),
    ("Jeddah Waterfront Residences", "Residential"),
    ("Dammam Industrial Warehouse Complex", "Warehouse"),
    ("Makkah Transit Station Package 3", "Infrastructure"),
    ("Madinah Community School Campus", "School"),
    ("Northern Coastal Access Road", "Infrastructure"),
    ("Khobar Corniche Residential Towers", "Residential"),
]

RFI_SUBJECTS = [
    "Rebar spacing clarification at core wall",
    "Curtain wall connection detail",
    "MEP routing conflict above ceiling",
    "Foundation waterproofing specification",
    "Fire-rated door schedule confirmation",
    "Concrete mix design approval",
]
CO_DESCRIPTIONS = [
    "Additional excavation for unforeseen rock",
    "Upgraded facade cladding to client request",
    "Extended MEP scope for added floor",
    "Revised landscaping to updated master plan",
]
CLAIM_NARRATIVES = [
    "Prolongation costs due to delayed site access.",
    "Additional works arising from design changes.",
    "Acceleration costs to recover programme slippage.",
]
SITE_SUMMARIES = [
    "Concrete pour completed for level slab; no safety incidents reported.",
    "Blockwork ongoing; two subcontractor crews mobilised on site.",
    "MEP first-fix in progress; minor delay due to material delivery.",
    "Facade installation started on the north elevation.",
]
DELAY_CAUSES = ["Supplier delay", "Customs clearance", "Fabrication rework", "Transport disruption"]


class DemoDataExists(RuntimeError):
    """Raised when the target database already contains projects and force is not set."""


async def _ensure_users(db: AsyncSession) -> None:
    for email, full_name, role in DEMO_USERS:
        if await user_service.get_user_by_email(db, email) is None:
            await user_service.create_user(
                db, email=email, full_name=full_name, role=role.value, password=DEV_PASSWORD
            )


async def _get_or_create_client(db: AsyncSession, name: str, cache: dict[str, Client]) -> Client:
    if name in cache:
        return cache[name]
    client = await db.scalar(select(Client).where(Client.name == name))
    if client is None:
        client = Client(name=name)
        db.add(client)
        await db.flush()
    cache[name] = client
    return client


async def seed_demo(db: AsyncSession, *, force: bool = False) -> dict[str, int]:
    """Create the demo portfolio and return a per-entity count (deterministic for a given DB)."""
    existing = await db.scalar(select(func.count()).select_from(Project))
    if existing and not force:
        raise DemoDataExists(
            f"Database already has {existing} project(s); refusing to seed demo data. "
            "Set FORCE_DEMO_SEED=1 to override."
        )

    rng = random.Random(2026)
    counts = dict.fromkeys(
        (
            "projects", "suppliers", "rfis", "meetings", "site_reports",
            "change_orders", "claims", "purchase_requests", "purchase_orders",
        ),
        0,
    )
    client_cache: dict[str, Client] = {}

    await _ensure_users(db)

    suppliers: list[Supplier] = []
    for i, name in enumerate(SUPPLIERS):
        supplier = await db.scalar(select(Supplier).where(Supplier.supplier_name == name))
        if supplier is None:
            supplier = Supplier(
                supplier_name=name,
                category=MATERIALS[i % len(MATERIALS)],
                city=rng.choice(CITIES),
                status="Active",
            )
            db.add(supplier)
            await db.flush()
            counts["suppliers"] += 1
        suppliers.append(supplier)

    for idx, (project_name, project_type) in enumerate(PROJECTS, start=1):
        code = f"DEMO-P{idx:02d}"
        if await db.scalar(select(Project).where(Project.project_code == code)):
            continue
        client = await _get_or_create_client(db, rng.choice(CLIENTS), client_cache)
        start = TODAY - timedelta(days=rng.randint(120, 600))
        project = Project(
            project_code=code,
            project_name=project_name,
            project_type=project_type,
            client_id=client.id,
            client_name=client.name,
            city=rng.choice(CITIES),
            start_date=start,
            planned_finish=start + timedelta(days=rng.randint(400, 900)),
            status=rng.choice(["Active", "Active", "Delayed", "On Hold"]),
            budget=Decimal(rng.randint(20, 500)) * Decimal("1000000"),
        )
        db.add(project)
        await db.flush()
        counts["projects"] += 1

        for r in range(rng.randint(2, 4)):
            raised = TODAY - timedelta(days=rng.randint(5, 90))
            overdue = rng.random() < 0.4
            db.add(
                Rfi(
                    project_id=project.id,
                    rfi_number=f"{code}-RFI-{r + 1:02d}",
                    subject=rng.choice(RFI_SUBJECTS),
                    question="Please review and confirm the attached detail for construction.",
                    discipline=rng.choice(DISCIPLINES),
                    raised_by="Main Contractor",
                    assigned_to="Design Consultant",
                    raised_date=raised,
                    required_date=raised + timedelta(days=rng.randint(7, 21)),
                    status="Open" if overdue else rng.choice(["Open", "Answered", "Closed"]),
                    priority=rng.choice(["Low", "Medium", "High", "High"]),
                )
            )
            counts["rfis"] += 1

        for m in range(rng.randint(2, 3)):
            meeting_type = rng.choice(MEETING_TYPES)
            db.add(
                Meeting(
                    project_id=project.id,
                    title=f"{meeting_type} — Week {m + 1}",
                    meeting_type=meeting_type,
                    meeting_date=TODAY - timedelta(days=rng.randint(1, 60)),
                )
            )
            counts["meetings"] += 1

        for _ in range(rng.randint(3, 5)):
            db.add(
                SiteReport(
                    project_id=project.id,
                    report_date=TODAY - timedelta(days=rng.randint(1, 45)),
                    weather=rng.choice(WEATHER),
                    summary=rng.choice(SITE_SUMMARIES),
                )
            )
            counts["site_reports"] += 1

        for c in range(rng.randint(1, 2)):
            db.add(
                ChangeOrder(
                    project_id=project.id,
                    co_number=f"{code}-CO-{c + 1:02d}",
                    description=rng.choice(CO_DESCRIPTIONS),
                    value=Decimal(rng.randint(50, 800)) * Decimal("1000"),
                    status=rng.choice(["Pending", "Approved", "Rejected"]),
                )
            )
            counts["change_orders"] += 1

        for cl in range(rng.randint(0, 2)):
            db.add(
                Claim(
                    project_id=project.id,
                    claim_number=f"{code}-CLM-{cl + 1:02d}",
                    claim_type=rng.choice(["Cost", "EOT", "Variation"]),
                    amount=Decimal(rng.randint(100, 2000)) * Decimal("1000"),
                    status=rng.choice(["Submitted", "Under Review", "Approved"]),
                    narrative=rng.choice(CLAIM_NARRATIVES),
                )
            )
            counts["claims"] += 1

        for pr in range(rng.randint(3, 5)):
            incomplete = rng.random() < 0.25
            request = PurchaseRequest(
                project_id=project.id,
                request_no=f"{code}-PR-{pr + 1:02d}",
                material_category=None if incomplete else rng.choice(MATERIALS),
                specification=None if incomplete else "As per approved project specification.",
                required_delivery_date=TODAY + timedelta(days=rng.randint(10, 90)),
                status=rng.choice(["Under Review", "Approved", "Converted to PO"]),
                created_at=TODAY - timedelta(days=rng.randint(10, 60)),
            )
            db.add(request)
            await db.flush()
            counts["purchase_requests"] += 1

            if rng.random() < 0.6:
                promised = TODAY - timedelta(days=rng.randint(5, 60))
                if rng.random() < 0.4:
                    actual = promised + timedelta(days=rng.randint(3, 20))
                else:
                    actual = promised - timedelta(days=rng.randint(0, 3))
                delay_days = max((actual - promised).days, 0)
                db.add(
                    PurchaseOrder(
                        pr_id=request.id,
                        project_id=project.id,
                        supplier_id=rng.choice(suppliers).id,
                        po_number=f"{code}-PO-{pr + 1:02d}",
                        issue_date=promised - timedelta(days=rng.randint(20, 40)),
                        promised_delivery=promised,
                        actual_delivery=actual,
                        status="Delivered",
                        is_late=delay_days > 0,
                        delay_days=delay_days,
                        delay_root_cause=rng.choice(DELAY_CAUSES) if delay_days > 0 else None,
                    )
                )
                counts["purchase_orders"] += 1

    return counts


async def run() -> None:
    force = os.getenv("FORCE_DEMO_SEED") == "1"
    async with AsyncSessionLocal() as db:
        try:
            counts = await seed_demo(db, force=force)
        except DemoDataExists as exc:
            print(f"skipped: {exc}")
            await engine.dispose()
            return
        await db.commit()

    for entity, count in counts.items():
        print(f"{entity}: {count}")
    print(f"dev password for all seeded accounts: {DEV_PASSWORD}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
