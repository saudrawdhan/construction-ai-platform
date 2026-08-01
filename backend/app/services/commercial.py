from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChangeOrder,
    Claim,
    ClaimEvidence,
    Correspondence,
    Document,
    ProjectDecision,
)
from app.schemas.commercial import (
    ChangeOrderCreate,
    ChangeOrderImpact,
    ChangeOrderRead,
    ChangeOrderUpdate,
    ClaimCreate,
    ClaimEvidenceChain,
    ClaimRead,
    ClaimUpdate,
    CorrespondenceBrief,
    DecisionBrief,
    DocumentBrief,
    EvidenceItem,
)


async def create_change_order(db: AsyncSession, payload: ChangeOrderCreate) -> ChangeOrder:
    change_order = ChangeOrder(**payload.model_dump())
    db.add(change_order)
    await db.flush()
    return change_order


async def update_change_order(
    db: AsyncSession, co_id: int, payload: ChangeOrderUpdate
) -> ChangeOrder | None:
    change_order = await db.get(ChangeOrder, co_id)
    if change_order is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(change_order, field, value)
    await db.flush()
    return change_order


async def delete_change_order(db: AsyncSession, co_id: int) -> bool:
    change_order = await db.get(ChangeOrder, co_id)
    if change_order is None:
        return False
    await db.delete(change_order)
    await db.flush()
    return True


async def create_claim(db: AsyncSession, payload: ClaimCreate) -> Claim:
    claim = Claim(**payload.model_dump())
    db.add(claim)
    await db.flush()
    return claim


async def update_claim(db: AsyncSession, claim_id: int, payload: ClaimUpdate) -> Claim | None:
    claim = await db.get(Claim, claim_id)
    if claim is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(claim, field, value)
    await db.flush()
    return claim


async def delete_claim(db: AsyncSession, claim_id: int) -> bool:
    claim = await db.get(Claim, claim_id)
    if claim is None:
        return False
    await db.delete(claim)
    await db.flush()
    return True


async def change_order_impact(db: AsyncSession, project_id: int) -> ChangeOrderImpact:
    """Aggregate a project's change orders into cost, programme, and cause.

    Every figure is computed here rather than narrated, so the numbers a commercial discussion
    turns on cannot be distorted by a model. Approved value is reported separately from total
    because an unapproved change order is a claim position, not yet a cost.
    """
    rows = list(
        await db.scalars(select(ChangeOrder).where(ChangeOrder.project_id == project_id))
    )
    by_cause: dict[str, int] = {}
    for row in rows:
        key = row.cause_category or "unspecified"
        by_cause[key] = by_cause.get(key, 0) + 1
    return ChangeOrderImpact(
        project_id=project_id,
        change_order_count=len(rows),
        total_value=sum((Decimal(str(r.value)) for r in rows), Decimal("0")),
        approved_value=sum(
            (Decimal(str(r.value)) for r in rows if r.status == "Approved"), Decimal("0")
        ),
        total_schedule_impact_days=sum(r.schedule_impact_days or 0 for r in rows),
        by_cause=dict(sorted(by_cause.items(), key=lambda item: (-item[1], item[0]))),
        caused_by_rfi_count=sum(1 for r in rows if r.cause_rfi_id is not None),
    )


async def list_change_orders(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    status: str | None = None,
) -> tuple[list[ChangeOrder], int]:
    query = select(ChangeOrder)
    if project_id:
        query = query.where(ChangeOrder.project_id == project_id)
    if status:
        query = query.where(ChangeOrder.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(ChangeOrder.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_change_order(db: AsyncSession, co_id: int) -> ChangeOrder | None:
    return await db.get(ChangeOrder, co_id)


async def list_claims(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    status: str | None = None,
    claim_type: str | None = None,
) -> tuple[list[Claim], int]:
    query = select(Claim)
    if project_id:
        query = query.where(Claim.project_id == project_id)
    if status:
        query = query.where(Claim.status == status)
    if claim_type:
        query = query.where(Claim.claim_type == claim_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(Claim.id).offset((page - 1) * size).limit(size))
    return list(rows), int(total or 0)


async def get_claim(db: AsyncSession, claim_id: int) -> Claim | None:
    return await db.get(Claim, claim_id)


async def claim_evidence_chain(
    db: AsyncSession, claim_id: int
) -> ClaimEvidenceChain | None:
    claim = await db.get(Claim, claim_id)
    if claim is None:
        return None

    evidence_rows = await db.scalars(
        select(ClaimEvidence).where(ClaimEvidence.claim_id == claim_id)
    )

    items: list[EvidenceItem] = []
    for row in evidence_rows:
        change_order = await db.get(ChangeOrder, row.change_order_id)
        decision = await db.get(ProjectDecision, row.decision_id)
        document = await db.get(Document, row.document_id)
        correspondence = await db.get(Correspondence, row.correspondence_id)
        items.append(
            EvidenceItem(
                evidence_note=row.evidence_note,
                change_order=ChangeOrderRead.model_validate(change_order)
                if change_order
                else None,
                decision=DecisionBrief.model_validate(decision) if decision else None,
                document=DocumentBrief.model_validate(document) if document else None,
                correspondence=CorrespondenceBrief.model_validate(correspondence)
                if correspondence
                else None,
            )
        )

    return ClaimEvidenceChain(
        claim=ClaimRead.model_validate(claim),
        evidence_count=len(items),
        evidence=items,
    )
