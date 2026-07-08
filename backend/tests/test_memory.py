from sqlalchemy import func, select

from app.models import AiAuditLog


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
