"""Deterministic seeder for the project registers the source dataset does not carry: risks,
issues, milestones, meeting action items, and change-order cause/impact.

The tables were migrated from the start but never populated, so every project's Risk Register
rendered empty and the copilot's "unresolved action items" had nothing to answer from — a feature
that works but looks broken. Content is drawn from realistic Saudi construction scenarios and
scaled to each project's own status and programme dates, so a delayed project genuinely carries
more open risk than one running normally.

Seeded with a fixed RNG so every run reproduces the same demo data.
"""

import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import func, select, text

from app.database.session import AsyncSessionLocal, engine
from app.models import (
    ChangeOrder,
    Meeting,
    MeetingActionItem,
    Project,
    ProjectIssue,
    ProjectMilestone,
    ProjectRisk,
    Rfi,
)

RNG = random.Random(42)
TODAY = date(2026, 7, 6)

RISKS = [
    (
        "Differential settlement at foundation grid",
        "Survey shows movement beyond tolerance; structural review required before backfill.",
        "High",
    ),
    (
        "Long-lead switchgear delivery slipping",
        "Supplier confirmed a revised date past the MEP first-fix window.",
        "High",
    ),
    (
        "Curtain wall shop drawings pending approval",
        "Consultant review is holding fabrication release.",
        "Medium",
    ),
    (
        "Concrete supply constrained during peak pour",
        "Batching plant capacity shared with two other sites in the area.",
        "Medium",
    ),
    (
        "Skilled manpower shortfall on finishing works",
        "Subcontractor mobilization below the agreed histogram.",
        "Medium",
    ),
    (
        "Access road congestion limiting deliveries",
        "Municipality works restrict heavy vehicle movement to night hours.",
        "Low",
    ),
    (
        "Summer heat restrictions reducing productive hours",
        "Midday work ban compresses the daily output window.",
        "Medium",
    ),
    (
        "Unresolved client scope change on level 3",
        "Awaiting written instruction; cost and time impact not yet agreed.",
        "High",
    ),
    (
        "Dewatering pump capacity below inflow rate",
        "Groundwater higher than the geotechnical report indicated.",
        "High",
    ),
    (
        "Fire alarm cause-and-effect matrix not approved",
        "Testing and commissioning sequence cannot be finalized.",
        "Low",
    ),
]

ISSUES = [
    (
        "Rebar delivery rejected at gate",
        "Mill certificates did not match the approved submittal.",
    ),
    (
        "Temporary power outage stopped tower crane",
        "Generator changeover failed during the morning shift.",
    ),
    (
        "Discrepancy between architectural and MEP drawings",
        "Ceiling void insufficient for the coordinated services.",
    ),
    (
        "Site accommodation permit expired",
        "Renewal pending with the municipality.",
    ),
    (
        "Damaged waterproofing membrane at basement wall",
        "Detected during inspection; rework required before backfill.",
    ),
    (
        "Subcontractor invoice dispute delaying progress",
        "Measurement disagreement on blockwork quantities.",
    ),
    (
        "Survey benchmark disturbed by earthworks",
        "Re-establishment required before column setting out.",
    ),
    (
        "Material laydown area flooded after rainfall",
        "Drainage insufficient; stored materials to be relocated.",
    ),
]

MILESTONES = [
    ("Site mobilization complete", 0.05),
    ("Foundations complete", 0.25),
    ("Structural frame topped out", 0.50),
    ("Building watertight", 0.68),
    ("MEP first fix complete", 0.80),
    ("Testing and commissioning complete", 0.93),
    ("Handover to client", 1.00),
]

ACTIONS = [
    ("Issue the revised recovery schedule to the client", "Project Manager"),
    ("Close out the open NCRs raised this month", "QA/QC Manager"),
    ("Expedite the long-lead switchgear order", "Procurement Officer"),
    ("Submit the curtain wall shop drawings for approval", "Design Coordinator"),
    ("Confirm the additional manpower histogram", "Construction Manager"),
    ("Provide the cost impact assessment for the scope change", "Commercial Manager"),
    ("Update the site safety induction records", "HSE Officer"),
    ("Reconcile the blockwork measurement with the subcontractor", "Quantity Surveyor"),
]

# Why change orders happen on a real site, weighted so design changes and client instructions
# dominate the way they do in practice rather than being spread evenly.
CO_CAUSES = [
    ("design_change", "Revised design issued after coordination review.", 12),
    ("client_instruction", "Client instructed an upgrade to the specified finish.", 10),
    ("site_condition", "Unforeseen ground condition encountered during excavation.", 20),
    ("regulatory", "Authority required an additional life-safety provision.", 15),
    ("error_or_omission", "Missing scope identified in the tender documents.", 8),
    ("other", "Scope adjustment agreed in the monthly progress meeting.", 5),
]

RISK_STATUSES = ["Open", "Open", "Open", "Mitigated", "Closed"]
ISSUE_STATUSES = ["Open", "Open", "In Progress", "Resolved", "Closed"]
# Matches the Add Risk form's own options exactly (SEVERITIES / LIKELIHOODS in ProjectDetail),
# so a seeded row and a user-created one never show two different vocabularies in one column.
LIKELIHOODS = ["Low", "Medium", "High"]
OWNERS = [
    "Eng. Salem Al-Harbi", "Eng. Noura Al-Qahtani", "Eng. Faisal Al-Otaibi",
    "Eng. Huda Al-Zahrani", "Eng. Turki Al-Dosari",
]


def _fraction_date(start: date, finish: date, fraction: float) -> date:
    return start + timedelta(days=int((finish - start).days * fraction))


def _troubled(project: Project) -> bool:
    return project.status in ("Delayed", "On Hold")


def build_risks(projects: list[Project]) -> list[dict]:
    rows = []
    for project in projects:
        # A delayed project should read as carrying more live risk than a healthy one, otherwise
        # the register looks the same everywhere and tells a manager nothing.
        count = RNG.randint(4, 6) if _troubled(project) else RNG.randint(2, 4)
        for title, description, severity in RNG.sample(RISKS, count):
            status = RNG.choice(RISK_STATUSES[:4] if _troubled(project) else RISK_STATUSES)
            rows.append(
                {
                    "project_id": project.id,
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "likelihood": RNG.choice(LIKELIHOODS),
                    "status": status,
                    "owner": RNG.choice(OWNERS),
                }
            )
    return rows


def build_issues(projects: list[Project]) -> list[dict]:
    rows = []
    for project in projects:
        count = RNG.randint(2, 4) if _troubled(project) else RNG.randint(1, 3)
        for title, description in RNG.sample(ISSUES, count):
            rows.append(
                {
                    "project_id": project.id,
                    "title": title,
                    "description": description,
                    "status": RNG.choice(ISSUE_STATUSES),
                    "owner": RNG.choice(OWNERS),
                }
            )
    return rows


def build_milestones(projects: list[Project]) -> list[dict]:
    rows = []
    for project in projects:
        start = project.start_date or date(2023, 1, 1)
        finish = project.planned_finish or (start + timedelta(days=540))
        # A construction programme is sequential: once a milestone slips, nothing downstream of
        # it can be complete. Tracking the first slip keeps the register physically possible —
        # without it the data reads as a building made watertight before its frame topped out.
        slipped = False
        for name, fraction in MILESTONES:
            planned = _fraction_date(start, finish, fraction)
            if slipped:
                status = "Delayed" if planned < TODAY else "Pending"
                actual = None
            elif planned < TODAY:
                # A milestone whose planned date has passed is either done or visibly late; a
                # troubled project is likelier to be the latter.
                late = RNG.random() < (0.45 if _troubled(project) else 0.15)
                status = "Delayed" if late else "Completed"
                actual = None if late else planned + timedelta(days=RNG.randint(-5, 12))
                slipped = late
            else:
                status = "Pending"
                actual = None
            rows.append(
                {
                    "project_id": project.id,
                    "name": name,
                    "planned_date": planned,
                    "actual_date": actual,
                    "status": status,
                }
            )
    return rows


def build_action_items(meetings: list[Meeting]) -> list[dict]:
    rows = []
    for meeting in meetings:
        for description, owner in RNG.sample(ACTIONS, RNG.randint(1, 3)):
            base = meeting.meeting_date or TODAY - timedelta(days=30)
            due = base + timedelta(days=RNG.randint(7, 45))
            # Leave a genuine overdue backlog so the "unresolved action items" surface and the
            # agent's overdue count have something real to report.
            status = "Open" if (due < TODAY and RNG.random() < 0.6) else RNG.choice(
                ["Open", "Closed", "Closed"]
            )
            rows.append(
                {
                    "meeting_id": meeting.id,
                    "project_id": meeting.project_id,
                    "description": description,
                    "owner": owner,
                    "due_date": due,
                    "status": status,
                }
            )
    return rows


def build_change_order_updates(
    change_orders: list[ChangeOrder], rfis_by_project: dict[int, list[int]]
) -> list[dict]:
    """Attach a cause and a programme impact to every change order.

    Roughly half are linked to the RFI that triggered them, which is the realistic pattern: a
    change often begins as a question about the design, but plenty originate on site or by direct
    instruction and have no RFI behind them at all.
    """
    updates = []
    for change_order in change_orders:
        category, description, max_days = RNG.choice(CO_CAUSES)
        candidates = rfis_by_project.get(change_order.project_id, [])
        link_rfi = category in ("design_change", "error_or_omission") and bool(candidates)
        updates.append(
            {
                "co_id": change_order.id,
                "cause_category": category,
                "cause_description": description,
                "schedule_impact_days": RNG.randint(0, max_days),
                "cause_rfi_id": RNG.choice(candidates) if link_rfi else None,
            }
        )
    return updates


async def run() -> None:
    async with AsyncSessionLocal() as session:
        projects = list((await session.scalars(select(Project).order_by(Project.id))).all())
        # Action items hang off meetings; a bounded sample keeps the register readable rather
        # than burying a project's real follow-ups under hundreds of rows.
        meetings = list(
            (await session.scalars(select(Meeting).order_by(Meeting.id).limit(120))).all()
        )

        await session.execute(
            text(
                "TRUNCATE project_risks, project_issues, project_milestones, "
                "meeting_action_items RESTART IDENTITY"
            )
        )
        await session.execute(ProjectRisk.__table__.insert(), build_risks(projects))
        await session.execute(ProjectIssue.__table__.insert(), build_issues(projects))
        await session.execute(ProjectMilestone.__table__.insert(), build_milestones(projects))
        await session.execute(MeetingActionItem.__table__.insert(), build_action_items(meetings))

        # Change orders already exist; only their cause and programme impact are added, so this
        # updates in place rather than truncating real commercial records.
        change_orders = list((await session.scalars(select(ChangeOrder))).all())
        rfis_by_project: dict[int, list[int]] = {}
        for rfi_id, rfi_project in await session.execute(select(Rfi.id, Rfi.project_id)):
            rfis_by_project.setdefault(rfi_project, []).append(rfi_id)
        for update in build_change_order_updates(change_orders, rfis_by_project):
            await session.execute(
                ChangeOrder.__table__.update()
                .where(ChangeOrder.id == update.pop("co_id"))
                .values(**update)
            )
        await session.commit()

        async def _count(model, *where) -> int:
            stmt = select(func.count()).select_from(model)
            for clause in where:
                stmt = stmt.where(clause)
            return int(await session.scalar(stmt) or 0)

        risks = await _count(ProjectRisk)
        open_risks = await _count(ProjectRisk, ProjectRisk.status == "Open")
        issues = await _count(ProjectIssue)
        milestones = await _count(ProjectMilestone)
        delayed = await _count(ProjectMilestone, ProjectMilestone.status == "Delayed")
        actions = await _count(MeetingActionItem)
        overdue = await _count(
            MeetingActionItem,
            MeetingActionItem.status == "Open",
            MeetingActionItem.due_date < TODAY,
        )
        co_total = await _count(ChangeOrder, ChangeOrder.cause_category.is_not(None))
        co_linked = await _count(ChangeOrder, ChangeOrder.cause_rfi_id.is_not(None))

    print(f"projects seeded against : {len(projects)}")
    print(f"project_risks           : {risks} ({open_risks} open)")
    print(f"project_issues          : {issues}")
    print(f"project_milestones      : {milestones} ({delayed} delayed)")
    print(f"meeting_action_items    : {actions} ({overdue} open and overdue)")
    print(f"change_orders enriched  : {co_total} ({co_linked} linked to a causing RFI)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
