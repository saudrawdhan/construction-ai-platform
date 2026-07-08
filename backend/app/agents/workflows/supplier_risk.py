"""Supplier Risk workflow (spec 9). Scores a supplier from cross-project delivery and quality
signals, persists a supplier_evaluations row so risk history accumulates, and writes a
supplier_performance memory for future reuse.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows.base import clamp, gather_memory_context
from app.models import SupplierEvaluation
from app.schemas.memory import MemoryCategory, MemoryCreate
from app.schemas.workflows import SupplierRiskAssessment
from app.services.audit import log_ai_call
from app.services.embeddings import get_embedder
from app.services.llm import LLMClient
from app.services.memory import create_memory
from app.services.procurement import supplier_performance


def _risk_level(score: float) -> str:
    return "Low" if score < 30 else "Medium" if score < 60 else "High"


async def run(
    db: AsyncSession, *, supplier_id: int, llm: LLMClient
) -> SupplierRiskAssessment | None:
    performance = await supplier_performance(db, supplier_id)
    if performance is None:
        return None

    has_history = performance.total_purchase_orders > 0
    if has_history:
        score = round(
            clamp(
                (100 - performance.on_time_rate) * 0.6
                + min(performance.ncr_count * 3, 25)
                + min(performance.average_delay_days_when_late, 25),
                0,
                100,
            ),
            1,
        )
        level = _risk_level(score)
    else:
        # No delivery history — do not fabricate a lateness-based score.
        score = round(min(performance.ncr_count * 5, 100), 1)
        level = "Unrated" if performance.ncr_count == 0 else _risk_level(score)

    drivers: list[str] = []
    if not has_history:
        drivers.append("No purchase-order history yet — risk cannot be fully assessed")
    if has_history and performance.on_time_rate < 80:
        drivers.append(f"On-time delivery only {performance.on_time_rate}%")
    if performance.ncr_count:
        drivers.append(f"{performance.ncr_count} non-conformance report(s)")
    if has_history and performance.average_delay_days_when_late:
        drivers.append(
            f"Average {performance.average_delay_days_when_late} days late when delayed"
        )
    for cause in performance.top_delay_causes[:2]:
        drivers.append(f"Recurring cause: {cause.cause} ({cause.count})")

    memory_context, memory_ids = await gather_memory_context(
        db,
        query=f"supplier {performance.supplier_name} performance risk delays",
        category="supplier_performance",
        k=3,
    )

    if not has_history:
        recommendation = (
            f"{performance.supplier_name} has no purchase-order history yet; monitor initial "
            "deliveries before relying on this supplier for critical scopes."
        )
    else:
        recommendation = (
            f"{performance.supplier_name} is a {level.lower()}-risk supplier (score {score}). "
            + (
                "Restrict to non-critical scopes and require recovery commitments."
                if level == "High"
                else "Monitor delivery performance on active orders."
                if level == "Medium"
                else "Continue as an approved supplier."
            )
        )

    if llm.provider != "mock":
        context = (
            f"Supplier: {performance.supplier_name}\n"
            f"on_time_rate={performance.on_time_rate}% late_pos={performance.late_purchase_orders} "
            f"ncr_count={performance.ncr_count} avg_delay_when_late="
            f"{performance.average_delay_days_when_late}\n"
            f"drivers: {drivers}\n"
            f"prior memories:\n{memory_context}\n"
            "Write one concise, business-oriented risk recommendation for management."
        )
        result = await llm.complete(
            system="You are a construction procurement risk analyst. Be concise and practical.",
            messages=[{"role": "user", "content": context}],
            max_tokens=512,
        )
        recommendation = result.text.strip() or recommendation

    evaluation = SupplierEvaluation(
        supplier_id=supplier_id,
        evaluation_date=date.today(),
        risk_score=score,
        on_time_rate=performance.on_time_rate,
        late_po_count=performance.late_purchase_orders,
        ncr_count=performance.ncr_count,
        delay_days_total=performance.total_delay_days,
        summary=recommendation,
        generated_by="agent",
    )
    db.add(evaluation)
    await db.flush()

    await create_memory(
        db,
        get_embedder(),
        MemoryCreate(
            category=MemoryCategory.SUPPLIER_PERFORMANCE,
            summary=f"{performance.supplier_name}: {level} risk (score {score}), "
            f"on-time {performance.on_time_rate}%, {performance.ncr_count} NCRs.",
            detail=recommendation,
            source_type="supplier_evaluation",
            source_id=evaluation.id,
            confidence=0.8,
        ),
        created_by="agent",
    )

    await log_ai_call(
        db,
        workflow="supplier_risk",
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
        source_ids={"supplier": supplier_id, "memory": memory_ids},
        output_excerpt=recommendation,
    )

    return SupplierRiskAssessment(
        supplier_id=supplier_id,
        supplier_name=performance.supplier_name,
        risk_score=score,
        risk_level=level,
        on_time_rate=performance.on_time_rate,
        late_purchase_orders=performance.late_purchase_orders,
        ncr_count=performance.ncr_count,
        total_delay_days=performance.total_delay_days,
        drivers=drivers,
        recommendation=recommendation,
        evaluation_id=evaluation.id,
        memory_used=memory_ids,
        provider=llm.provider,
        model=getattr(llm, "model", "unknown"),
    )
