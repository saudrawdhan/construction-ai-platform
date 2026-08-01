from sqlalchemy import func, select

from app.agents.workflows.base import record_workflow_memory
from app.models import AiAuditLog, AiMemory, Supplier, SupplierEvaluation
from app.schemas.memory import MemoryCategory, MemoryCreate


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


async def _live_memories(db_session, source_type, source_id=None):
    query = select(AiMemory).where(
        AiMemory.source_type == source_type, AiMemory.superseded_by_id.is_(None)
    )
    if source_id is not None:
        query = query.where(AiMemory.source_id == source_id)
    return list(await db_session.scalars(query))


async def test_pr_review_records_a_procurement_blocker_memory(client, admin_headers, db_session):
    # Only three of the six workflows fed enterprise memory, so a reviewed purchase request left
    # nothing behind for a later review to learn from — half of the brief's headline promise.
    pr_id = await _incomplete_pr_id(client, admin_headers)
    await client.post(
        "/api/v1/procurement/purchase-requests/analyze",
        json={"pr_id": pr_id},
        headers=admin_headers,
    )
    memories = await _live_memories(db_session, "purchase_request", pr_id)
    assert len(memories) == 1
    assert memories[0].category == "procurement_blocker"


async def test_re_reviewing_a_purchase_request_does_not_duplicate_its_memory(
    client, admin_headers, db_session
):
    # A review can be re-run any number of times, but the request being incomplete is a property
    # of the record — it does not become truer on each pass, and must not multiply.
    pr_id = await _incomplete_pr_id(client, admin_headers)
    for _ in range(3):
        await client.post(
            "/api/v1/procurement/purchase-requests/analyze",
            json={"pr_id": pr_id},
            headers=admin_headers,
        )
    assert len(await _live_memories(db_session, "purchase_request", pr_id)) == 1


async def test_rfi_escalation_records_the_backlog(client, admin_headers, db_session):
    await client.post("/api/v1/rfis/32/analyze", headers=admin_headers)
    memories = await _live_memories(db_session, "rfi_escalation", 32)
    assert len(memories) == 1
    assert memories[0].category == "issue"


async def test_re_running_rfi_escalation_on_an_unchanged_backlog_keeps_one_live_memory(
    client, admin_headers, db_session
):
    # An unchanged backlog produces an identical summary, which create_memory recognizes as an
    # exact repeat and returns the existing record for. The record must survive that untouched:
    # an earlier version of the supersede logic pointed the row at itself, setting its own
    # superseded_by_id and silently removing the finding from every search.
    await client.post("/api/v1/rfis/32/analyze", headers=admin_headers)
    first = await _live_memories(db_session, "rfi_escalation", 32)
    assert len(first) == 1

    await client.post("/api/v1/rfis/32/analyze", headers=admin_headers)
    live = await _live_memories(db_session, "rfi_escalation", 32)
    assert len(live) == 1
    assert live[0].id == first[0].id
    assert live[0].superseded_by_id is None


async def test_workflow_memory_serializes_concurrent_writes_for_the_same_source(db_session):
    # Guards the advisory lock that makes the check-then-write section atomic. A genuine race
    # needs separate committed transactions, which this suite's single rolled-back transaction
    # cannot express, so the behaviour was proven live instead (six concurrent writes produced
    # six live rows before the lock and exactly one after). What is asserted here is that the
    # lock is actually taken — without it the live proof silently regresses to the broken case.
    from unittest.mock import patch

    executed: list[str] = []
    original = db_session.execute

    async def _record(statement, *args, **kwargs):
        executed.append(str(statement))
        return await original(statement, *args, **kwargs)

    with patch.object(db_session, "execute", _record):
        await record_workflow_memory(
            db_session,
            data=MemoryCreate(
                project_id=3, category=MemoryCategory.ISSUE, summary="Lock probe.",
                source_type="lock_probe", source_id=3, confidence=0.7,
            ),
        )
    assert any("pg_advisory_xact_lock" in statement for statement in executed)


async def test_supersede_replaces_the_live_memory_when_the_finding_changes(db_session):
    # The moving-position case the supersede flag exists for: a genuinely changed finding
    # replaces its predecessor, which stays on file as history but leaves retrieval.
    def _payload(summary):
        return MemoryCreate(
            project_id=32, category=MemoryCategory.ISSUE, summary=summary,
            source_type="rfi_escalation_probe", source_id=32, confidence=0.7,
        )

    first = await record_workflow_memory(db_session, data=_payload("4 overdue RFIs."))
    second = await record_workflow_memory(
        db_session, data=_payload("9 overdue RFIs."), supersede=True
    )
    assert second is not None and second.id != first.id
    assert first.superseded_by_id == second.id
    live = await _live_memories(db_session, "rfi_escalation_probe", 32)
    assert [m.id for m in live] == [second.id]


async def test_rfi_escalation_records_nothing_when_no_rfis_are_overdue(
    client, admin_headers, db_session
):
    # A clean project carries no lesson; recording "nothing is wrong" every run would be noise.
    response = await client.post("/api/v1/rfis/999999/analyze", headers=admin_headers)
    assert response.status_code in {200, 404}
    if response.status_code == 200 and response.json()["overdue_count"] == 0:
        assert await _live_memories(db_session, "rfi_escalation", 999999) == []


async def test_executive_report_memory_supersedes_instead_of_accumulating(
    client, admin_headers, db_session
):
    # The weekly scheduled run calls this with store=True. Appending would add a near-identical
    # row every week and steadily crowd real lessons out of retrieval, so it must supersede.
    for _ in range(3):
        await client.post(
            "/api/v1/reports/executive-weekly", json={"store": True}, headers=admin_headers
        )
    assert len(await _live_memories(db_session, "executive_report")) == 1


async def test_executive_report_writes_no_memory_when_not_storing(
    client, admin_headers, db_session
):
    await client.post(
        "/api/v1/reports/executive-weekly", json={"store": False}, headers=admin_headers
    )
    assert await _live_memories(db_session, "executive_report") == []


def test_localize_leaves_english_prompts_untouched():
    # English is the prompts' own language, so the default path must stay byte-identical to how
    # every workflow behaved before language handling existed.
    from app.agents.workflows.base import localize

    assert localize("Base prompt.", "en") == "Base prompt."
    assert localize("Base prompt.", "") == "Base prompt."
    assert localize("Base prompt.", "fr") == "Base prompt."


def test_localize_asks_for_arabic_prose_and_protects_json_keys():
    # A translated JSON key silently breaks extraction while still looking like a valid answer,
    # so the JSON variant must pin the field names to English.
    from app.agents.workflows.base import localize

    prose = localize("Base prompt.", "ar")
    assert "العربية" in prose
    assert "JSON" not in prose

    structured = localize("Base prompt.", "ar", json_mode=True)
    assert "العربية" in structured
    assert "field NAMES must stay exactly as specified in English" in structured


def test_request_language_reads_the_header_and_falls_back_safely():
    from app.api.deps import request_language

    assert request_language("ar") == "ar"
    assert request_language("ar-SA,ar;q=0.9,en;q=0.8") == "ar"
    assert request_language("en-GB,en;q=0.9") == "en"
    assert request_language(None) == "en"
    assert request_language("") == "en"
    assert request_language("de") == "en"


def test_clean_narration_keeps_a_normal_answer_untouched():
    # The default path must not change: a well-formed answer in either language passes through
    # exactly as the model wrote it.
    from app.agents.workflows.base import clean_narration

    english = "Supplier 5 is a medium-risk supplier. Monitor delivery performance on open orders."
    arabic = "المورد رقم 5 متوسط المخاطر. يوصى بمتابعة أداء التسليم على الطلبات المفتوحة."
    assert clean_narration(english) == english
    assert clean_narration(arabic) == arabic
    assert clean_narration(f"  {english}  ") == english


def test_clean_narration_trims_a_hallucinated_conversation_turn():
    # Measured live: a 7B local model runs past its stop token and continues the transcript by
    # writing the next speaker's turn. Everything from that marker on is the model talking to
    # itself and must never reach the UI, the audit log, or enterprise memory.
    from app.agents.workflows.base import clean_narration

    answer = "Restrict this supplier to non-critical scopes and require recovery commitments."
    assert clean_narration(f"{answer}\nuser\nPlease continue in Arabic.") == answer
    assert clean_narration(f"{answer}\n assistant: more text") == answer
    assert clean_narration(f"{answer}<|im_end|><|im_start|>user") == answer
    assert clean_narration(f"{answer}</s>[INST] again [/INST]") == answer


def test_clean_narration_trims_a_language_breakout():
    # The platform only ever requests English or Arabic, so a run of CJK is the model switching
    # language mid-answer — observed live rewriting an entire Arabic escalation letter in Chinese.
    from app.agents.workflows.base import clean_narration

    arabic = "نوصي بتقييم تأثير التأخير المستمر في إجراءات الفحص المدني على الأداء العام."
    assert clean_narration(f"{arabic}按时翻译\nuser\n请用阿拉伯语继续。") == arabic


def test_clean_narration_does_not_trim_a_stray_fullwidth_punctuation_mark():
    # Calibration guard. The model sometimes closes a perfectly good Arabic letter with a fullwidth
    # comma instead of an Arabic one. That is a punctuation slip, not a language breakout, and
    # cutting there would throw away the signature block of a correct escalation email — which is
    # exactly what a single-character rule would have done. Only a genuine RUN of CJK counts.
    from app.agents.workflows.base import clean_narration

    letter = "شكرًا لتعاونكم في هذا الشأن العاجل.\n\nمع خالص التقدير والاحترام，\n\n[اسمك]"
    assert clean_narration(letter) == letter


def test_clean_narration_returns_empty_when_nothing_usable_survives():
    # Callers fall back to their own deterministic text via `or`, so an unusable generation must
    # yield "" rather than a truncated fragment being stored as if it were an answer.
    from app.agents.workflows.base import clean_narration

    assert clean_narration("") == ""
    assert clean_narration("   ") == ""
    assert clean_narration("user\nwhat now?") == ""


def test_clean_narration_holds_only_trimmed_text_to_a_length_floor():
    # A short answer that was never trimmed is still a valid answer — the agent's own synthesis
    # legitimately returns brief strings, and an untouched generation must pass through unchanged.
    # The floor exists only to stop a few characters left over from cutting mid-clause being
    # stored as if they were the answer.
    from app.agents.workflows.base import clean_narration

    assert clean_narration("Approved.") == "Approved."
    assert clean_narration("Yes.\nuser\nwhy?") == ""
