"""Purchase Request Review workflow (spec 9 + 11.2). Missing-field detection and supplier
history are computed deterministically for reliability; the LLM (real mode) refines the
recommendation and required approvals. Returns the structured fields the spec mandates.
"""

from datetime import date

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import PROCUREMENT_REVIEW_AGENT
from app.agents.workflows.base import (
    gather_memory_context,
    language_note,
    localize,
    parse_json_object,
    record_workflow_memory,
)
from app.models import PurchaseOrder, PurchaseRequest, Supplier
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import PurchaseRequestReview, SourceRef
from app.services.audit import log_ai_call
from app.services.llm import LLMClient

_APPROVALS = {
    "Low": ["Procurement Officer"],
    "Medium": ["Procurement Officer", "Project Manager"],
    "High": ["Procurement Officer", "Project Manager", "Commercial Manager"],
}


def _missing_fields(pr: PurchaseRequest) -> list[str]:
    missing = []
    if not pr.specification:
        missing.append("specification")
    if not pr.required_delivery_date:
        missing.append("required_delivery_date")
    if not pr.material_category:
        missing.append("material_category")
    return missing


def _base_risk(missing: list[str], pr: PurchaseRequest) -> str:
    level = "Low" if not missing else "Medium" if len(missing) == 1 else "High"
    if (
        level != "High"
        and pr.required_delivery_date
        and (pr.required_delivery_date - date.today()).days < 30
    ):
        level = "Medium" if level == "Low" else "High"
    return level


async def _category_late_rate(db: AsyncSession, category: str | None) -> float | None:
    if not category:
        return None
    rate = await db.scalar(
        select(func.avg(func.cast(PurchaseOrder.is_late, Integer)))
        .select_from(PurchaseOrder)
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .where(Supplier.category == category)
    )
    return round(float(rate) * 100, 1) if rate is not None else None


def _template_recommendation(missing: list[str], risk: str) -> str:
    if missing:
        return (
            f"Return to requester to complete: {', '.join(missing)}. "
            f"Risk assessed as {risk}; do not raise a PO until fields are complete."
        )
    return f"Proceed through the {risk}-risk approval route; information is complete."


async def run(
    db: AsyncSession, *, pr_id: int, llm: LLMClient, language: str = "en"
) -> PurchaseRequestReview | None:
    pr = await db.get(PurchaseRequest, pr_id)
    if pr is None:
        return None

    missing = _missing_fields(pr)
    risk = _base_risk(missing, pr)
    category = pr.material_category
    late_rate = await _category_late_rate(db, category)
    history_note = (
        f"Suppliers in category '{category}' have {late_rate}% historically late deliveries."
        if late_rate is not None
        else None
    )

    memory_context, memory_ids = await gather_memory_context(
        db,
        query=f"procurement risk {category or ''} {pr.specification or ''}",
        project_id=pr.project_id,
        category="procurement_blocker",
        k=3,
    )

    recommendation = _template_recommendation(missing, risk)
    approvals = _APPROVALS[risk]

    if llm.provider != "mock":
        context = (
            f"Purchase request {pr.request_no}\n"
            f"material_category: {category}\n"
            f"specification: {pr.specification}\n"
            f"required_delivery_date: {pr.required_delivery_date}\n"
            f"status: {pr.status}\n"
            f"Deterministically missing fields: {missing}\n"
            f"Supplier history: {history_note}\n"
            f"Related memories:\n{memory_context}\n"
            "Return JSON with material_category, missing_information, risk_level, "
            "recommendation, required_approvals."
            # Placed after the field list rather than only in the system prompt: that closing
            # instruction is the last thing the model reads, and it answered in English every
            # time while the language directive sat further back.
            + language_note(language, json_mode=True)
        )
        result = await llm.complete(
            system=localize(PROCUREMENT_REVIEW_AGENT, language, json_mode=True),
            messages=[{"role": "user", "content": context}],
            json_mode=True,
            max_tokens=1024,
        )
        parsed = parse_json_object(result.text)
        # The risk level and its approval route are computed deterministically and stay
        # authoritative — governance must not depend on model output. The model contributes only
        # the descriptive material category and the written recommendation.
        category = parsed.get("material_category") or category
        recommendation = parsed.get("recommendation") or recommendation

    # Only a review that actually found something is worth remembering: a complete, low-risk
    # request is the expected case and recording it would dilute the procurement history that
    # later reviews retrieve. Keyed to the request, so re-reviewing it never duplicates.
    if missing or risk == "High":
        await record_workflow_memory(
            db,
            data=MemoryCreate(
                project_id=pr.project_id,
                category=MemoryCategory.PROCUREMENT_BLOCKER,
                summary=(
                    f"PR {pr.request_no} ({category or 'uncategorized'}): {risk} risk. "
                    f"Missing: {', '.join(missing) if missing else 'nothing'}."
                ),
                detail=recommendation,
                source_type="purchase_request",
                source_id=pr.id,
                confidence=0.75,
            ),
        )

    await log_ai_call(
        db,
        workflow="pr_review",
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
        source_ids={"purchase_request": pr_id, "memory": memory_ids},
        output_excerpt=recommendation,
    )

    return PurchaseRequestReview(
        pr_id=pr.id,
        request_no=pr.request_no,
        material_category=category,
        missing_information=missing,
        risk_level=risk,
        recommendation=recommendation,
        required_approvals=list(approvals),
        supplier_history_note=history_note,
        sources=[SourceRef(type="purchase_request", id=pr.id)],
        memory_used=memory_ids,
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
    )
