from sqlalchemy import func, select

from app.models import AiAuditLog, AiMemory


async def test_create_and_get_memory(client, admin_headers):
    payload = {
        "project_id": 1,
        "category": "decision",
        "summary": "Procurement to expedite long-lead items and provide recovery schedule",
        "detail": "Agreed in technical coordination meeting.",
        "confidence": 0.9,
    }
    created = await client.post("/api/v1/memory/create", json=payload, headers=admin_headers)
    assert created.status_code == 201
    memory_id = created.json()["id"]
    assert created.json()["created_by"] == "user"

    fetched = await client.get(f"/api/v1/memory/{memory_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["category"] == "decision"


async def test_memory_search_finds_by_term(client, admin_headers):
    await client.post(
        "/api/v1/memory/create",
        json={
            "project_id": 2,
            "category": "procurement_blocker",
            "summary": "Supplier delayed long-lead switchgear affecting MEP works",
        },
        headers=admin_headers,
    )
    found = await client.get("/api/v1/memory/search?q=switchgear", headers=admin_headers)
    assert found.status_code == 200
    assert any("switchgear" in hit["memory"]["summary"] for hit in found.json()["results"])


async def test_search_ranks_higher_confidence_above_tied_relevance(client, admin_headers):
    # A deliberately poisoned pair (audit-style): two memories with IDENTICAL summary text so
    # their raw RRF relevance score is exactly tied, differing only in confidence and category
    # (different categories avoid the exact-duplicate dedup, which would otherwise collapse
    # them into one row). Before this fix, a low-confidence finding could rank above a
    # well-attested one purely by incidental tie-breaking; the reranking must put the
    # higher-confidence memory first whenever raw relevance is equal.
    summary = "Roof waterproofing membrane failure reported during inspection"
    low = await client.post(
        "/api/v1/memory/create",
        json={"project_id": 3, "category": "issue", "summary": summary, "confidence": 0.2},
        headers=admin_headers,
    )
    high = await client.post(
        "/api/v1/memory/create",
        json={"project_id": 3, "category": "risk", "summary": summary, "confidence": 0.95},
        headers=admin_headers,
    )
    assert low.status_code == 201
    assert high.status_code == 201
    assert low.json()["id"] != high.json()["id"]

    found = await client.get(
        "/api/v1/memory/search",
        params={"q": "roof waterproofing membrane"},
        headers=admin_headers,
    )
    assert found.status_code == 200
    ids_in_order = [hit["memory"]["id"] for hit in found.json()["results"]]
    assert high.json()["id"] in ids_in_order
    assert low.json()["id"] in ids_in_order
    assert ids_in_order.index(high.json()["id"]) < ids_in_order.index(low.json()["id"])


async def test_extract_is_deterministic_and_categorized(client, admin_headers):
    text = "Site team observed unsafe work at height; missing harness tie-off on scaffold."
    first = await client.post(
        "/api/v1/memory/extract", json={"text": text}, headers=admin_headers
    )
    second = await client.post(
        "/api/v1/memory/extract", json={"text": text}, headers=admin_headers
    )
    assert first.status_code == 200
    assert first.json()["provider"] == "mock"
    categories = [m["category"] for m in first.json()["extracted"]]
    assert "safety_event" in categories
    assert first.json()["extracted"] == second.json()["extracted"]


async def test_extract_store_reuse_loop(client, admin_headers, db_session):
    text = (
        "Decision: procurement team to expedite long-lead items. "
        "Risk of delay on the critical path if material delivery slips further."
    )
    extracted = await client.post(
        "/api/v1/memory/extract",
        json={"text": text, "project_id": 5, "store": True},
        headers=admin_headers,
    )
    assert extracted.status_code == 200
    assert len(extracted.json()["stored"]) >= 1

    # The reuse loop: a stored memory is now retrievable for future decisions.
    search = await client.get(
        "/api/v1/memory/search?q=expedite long-lead&project_id=5", headers=admin_headers
    )
    assert search.json()["count"] >= 1

    audit_count = await db_session.scalar(
        select(func.count()).select_from(AiAuditLog).where(
            AiAuditLog.workflow == "memory_extraction"
        )
    )
    assert audit_count >= 1


async def test_list_filter_by_category(client, admin_headers):
    await client.post(
        "/api/v1/memory/create",
        json={"project_id": 3, "category": "lesson_learned", "summary": "Sequence MEP earlier"},
        headers=admin_headers,
    )
    listed = await client.get(
        "/api/v1/memory?category=lesson_learned", headers=admin_headers
    )
    assert listed.status_code == 200
    assert all(m["category"] == "lesson_learned" for m in listed.json()["items"])


async def test_viewer_cannot_create_memory(client, viewer_headers):
    response = await client.post(
        "/api/v1/memory/create",
        json={"category": "risk", "summary": "should be blocked"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


async def test_exact_duplicate_memory_is_not_re_inserted(client, admin_headers, db_session):
    # Live audit testing found an exact-duplicate memory retrieved twice, verbatim, in
    # every matching search — pure noise. A repeat of the same summary in the same
    # project/category scope should return the existing record, not multiply it.
    payload = {
        "project_id": 4,
        "category": "supplier_performance",
        "summary": "Supplier 020: Medium risk (score 44.0), on-time 90.9%, 5 NCRs.",
    }
    before = await db_session.scalar(select(func.count()).select_from(AiMemory))
    first = await client.post("/api/v1/memory/create", json=payload, headers=admin_headers)
    second = await client.post(
        "/api/v1/memory/create",
        json={**payload, "summary": payload["summary"].upper() + "  "},
        headers=admin_headers,
    )
    after = await db_session.scalar(select(func.count()).select_from(AiMemory))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert after == before + 1


async def test_different_project_or_category_is_not_treated_as_a_duplicate(
    client, admin_headers, db_session
):
    same_summary = "Weather delays impacted the pour schedule this week."
    before = await db_session.scalar(select(func.count()).select_from(AiMemory))
    a = await client.post(
        "/api/v1/memory/create",
        json={"project_id": 5, "category": "risk", "summary": same_summary},
        headers=admin_headers,
    )
    b = await client.post(
        "/api/v1/memory/create",
        json={"project_id": 6, "category": "risk", "summary": same_summary},
        headers=admin_headers,
    )
    after = await db_session.scalar(select(func.count()).select_from(AiMemory))
    assert a.json()["id"] != b.json()["id"]
    assert after == before + 2


async def test_delete_memory(client, admin_headers, db_session):
    # A live audit test found no way to correct or remove a memory once created — a real gap
    # for a system where memory can legitimately be wrong (a mistaken manual entry, a bad
    # extraction, or something that turns out to no longer apply).
    created = await client.post(
        "/api/v1/memory/create",
        json={"project_id": 7, "category": "issue", "summary": "Delete-me test memory"},
        headers=admin_headers,
    )
    memory_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/memory/{memory_id}", headers=admin_headers)
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/memory/{memory_id}", headers=admin_headers)
    assert fetched.status_code == 404


async def test_delete_memory_missing_404(client, admin_headers):
    response = await client.delete("/api/v1/memory/999999", headers=admin_headers)
    assert response.status_code == 404


async def test_viewer_cannot_delete_memory(client, admin_headers, viewer_headers):
    created = await client.post(
        "/api/v1/memory/create",
        json={"project_id": 8, "category": "issue", "summary": "Viewer should not delete this"},
        headers=admin_headers,
    )
    memory_id = created.json()["id"]
    response = await client.delete(f"/api/v1/memory/{memory_id}", headers=viewer_headers)
    assert response.status_code == 403
