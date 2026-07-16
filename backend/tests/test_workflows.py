from sqlalchemy import func, select

from app.models import AiAuditLog, AiMemory, Supplier, SupplierEvaluation


async def _incomplete_pr_id(client, headers) -> int:
    response = await client.get(
        "/api/v1/procurement/purchase-requests?incomplete=true&size=1", headers=headers
    )
    return response.json()["items"][0]["id"]


async def test_pr_review_flags_missing_and_recommends(client, admin_headers):
    pr_id = await _incomplete_pr_id(client, admin_headers)
    response = await client.post(
        "/api/v1/procurement/purchase-requests/analyze",
        json={"pr_id": pr_id},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pr_id"] == pr_id
    assert len(body["missing_information"]) >= 1
    assert body["risk_level"] in {"Low", "Medium", "High"}
    assert body["required_approvals"]
    assert body["provider"] == "mock"


async def test_pr_review_missing_pr_404(client, admin_headers):
    response = await client.post(
        "/api/v1/procurement/purchase-requests/analyze",
        json={"pr_id": 999999},
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_pr_review_forbidden_for_viewer(client, viewer_headers):
    response = await client.post(
        "/api/v1/procurement/purchase-requests/analyze",
        json={"pr_id": 1},
        headers=viewer_headers,
    )
    assert response.status_code == 403


async def test_supplier_risk_writes_evaluation_and_memory(client, admin_headers, db_session):
    before_eval = await db_session.scalar(select(func.count()).select_from(SupplierEvaluation))
    before_mem = await db_session.scalar(select(func.count()).select_from(AiMemory))

    response = await client.post("/api/v1/suppliers/3/risk-assessment", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_level"] in {"Low", "Medium", "High"}
    assert body["evaluation_id"] is not None

    after_eval = await db_session.scalar(select(func.count()).select_from(SupplierEvaluation))
    after_mem = await db_session.scalar(select(func.count()).select_from(AiMemory))
    assert after_eval == before_eval + 1
    assert after_mem == before_mem + 1


async def test_supplier_risk_no_history_not_flagged_high(client, admin_headers, db_session):
    supplier = Supplier(
        supplier_name="Newly Onboarded Supplier",
        category="Civil",
        city="Riyadh",
        status="Active",
    )
    db_session.add(supplier)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/suppliers/{supplier.id}/risk-assessment", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["late_purchase_orders"] == 0
    # A supplier with no delivery history must not be fabricated as High risk.
    assert body["risk_level"] != "High"


async def test_rfi_escalation_returns_overdue(client, admin_headers):
    # project 32 has seeded overdue RFIs
    response = await client.post("/api/v1/rfis/32/analyze", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["overdue_count"] >= 1
    assert body["escalation_message"]
    assert all(item["days_overdue"] > 0 for item in body["items"])


async def test_workflows_write_audit_log(client, admin_headers, db_session):
    await client.post("/api/v1/rfis/32/analyze", headers=admin_headers)
    count = await db_session.scalar(
        select(func.count()).select_from(AiAuditLog).where(
            AiAuditLog.workflow == "rfi_escalation"
        )
    )
    assert count >= 1


class _RiskOverrideStubLLM:
    """A non-mock provider that returns an out-of-enum risk_level and a narrative, to prove the
    review keeps the deterministic risk and approval route while taking the model's wording."""

    provider = "local"
    model = "stub"

    async def complete(
        self, *, system, messages, temperature=0.2, max_tokens=None, json_mode=False
    ):
        from app.services.llm import LLMResult

        text = (
            '{"risk_level": "Catastrophic", "material_category": "Structural Steel", '
            '"recommendation": "Escalate to the commercial lead.", '
            '"required_approvals": ["Everyone"]}'
        )
        return LLMResult(text=text, model=self.model, provider=self.provider)


async def test_pr_review_keeps_deterministic_risk_and_approvals(db_session):
    from app.agents.workflows import pr_review

    review = await pr_review.run(db_session, pr_id=1, llm=_RiskOverrideStubLLM())
    assert review is not None
    assert review.risk_level in {"Low", "Medium", "High"}
    assert "Everyone" not in review.required_approvals
    assert review.material_category == "Structural Steel"
    assert review.recommendation == "Escalate to the commercial lead."
