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
    ChangeOrderRead,
    ClaimEvidenceChain,
    ClaimRead,
    CorrespondenceBrief,
    DecisionBrief,
    DocumentBrief,
    EvidenceItem,
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
