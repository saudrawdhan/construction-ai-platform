from app.models import AgentSkill


async def test_run_agent_endpoint_returns_trajectory(client, admin_headers):
    response = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Give an executive overview of the portfolio"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["step_count"] >= 2
    assert body["final_answer"]
    assert body["provider"] == "mock"
    assert body["id"]


async def test_run_agent_forbidden_for_viewer(client, viewer_headers):
    response = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Give an executive overview of the portfolio"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


async def test_agent_run_is_retrievable_and_listed(client, admin_headers):
    created = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    run_id = created.json()["id"]

    detail = await client.get(f"/api/v1/ai/agent/runs/{run_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["skill_created"]

    listing = await client.get("/api/v1/ai/agent/runs", headers=admin_headers)
    assert listing.status_code == 200
    assert any(item["id"] == run_id for item in listing.json()["items"])


async def test_agent_creates_then_lists_skill(client, admin_headers):
    await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skills = await client.get("/api/v1/ai/agent/skills", headers=admin_headers)
    assert skills.status_code == 200
    body = skills.json()
    assert len(body) == 1
    assert body[0]["status"] == "active"
    assert body[0]["parameters"]


async def test_run_skill_by_id_reuses_it(client, admin_headers):
    await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skills = await client.get("/api/v1/ai/agent/skills", headers=admin_headers)
    skill_id = skills.json()[0]["id"]

    reuse = await client.post(
        f"/api/v1/ai/agent/skills/{skill_id}/run",
        json={"goal": "Assess the risk of supplier 5"},
        headers=admin_headers,
    )
    assert reuse.status_code == 200
    body = reuse.json()
    assert body["skill_used"]
    supplier_step = next(s for s in body["steps"] if s["tool"] == "assess_supplier_risk")
    assert supplier_step["args"]["supplier_id"] == 5


async def test_run_missing_skill_404(client, admin_headers):
    response = await client.post(
        "/api/v1/ai/agent/skills/999999/run",
        json={"goal": "anything"},
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_agent_endpoint_enforces_tool_level_rbac(client, site_engineer_headers):
    # site_engineer CAN call the agent endpoint (200), but assess_supplier_risk is restricted
    # to admin/executive/procurement_officer at the direct endpoint — the run must complete
    # with a refusal for that specific tool, not silently execute it.
    response = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=site_engineer_headers,
    )
    assert response.status_code == 200
    body = response.json()
    supplier_step = next(s for s in body["steps"] if s["tool"] == "assess_supplier_risk")
    assert "not authorized" in supplier_step["observation"].lower()


async def test_agent_endpoint_allows_role_appropriate_tool(client, site_engineer_headers):
    response = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Check overdue RFIs for this project", "project_id": 1},
        headers=site_engineer_headers,
    )
    assert response.status_code == 200
    rfi_step = next(s for s in response.json()["steps"] if s["tool"] == "escalate_overdue_rfis")
    assert "not authorized" not in rfi_step["observation"].lower()


async def test_viewer_cannot_read_agent_runs_or_skills(client, admin_headers, viewer_headers):
    # AI-generated trajectories can surface output from tools a viewer could never call
    # directly (e.g. a supplier risk assessment). The platform's own precedent is that AI
    # outputs are never exposed to viewer (GET /audit/ai-outputs is admin/executive-only), so
    # the agent's run history and skill library must follow the same rule, not the more open
    # CurrentUser pattern used for plain business-record GET endpoints.
    created = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    run_id = created.json()["id"]

    assert (
        await client.get(f"/api/v1/ai/agent/runs/{run_id}", headers=viewer_headers)
    ).status_code == 403
    assert (
        await client.get("/api/v1/ai/agent/runs", headers=viewer_headers)
    ).status_code == 403
    assert (
        await client.get("/api/v1/ai/agent/skills", headers=viewer_headers)
    ).status_code == 403

    skills = await client.get("/api/v1/ai/agent/skills", headers=admin_headers)
    skill_id = skills.json()[0]["id"]
    assert (
        await client.get(f"/api/v1/ai/agent/skills/{skill_id}", headers=viewer_headers)
    ).status_code == 403


async def test_other_role_cannot_read_another_users_run(
    client, procurement_headers, site_engineer_headers
):
    # A run belongs to whoever created it. A different, non-oversight role must get the
    # same 404 whether the id is wrong or simply not theirs — confirming it exists at all
    # is the leak.
    created = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Give an executive overview of the portfolio"},
        headers=procurement_headers,
    )
    run_id = created.json()["id"]

    other = await client.get(f"/api/v1/ai/agent/runs/{run_id}", headers=site_engineer_headers)
    assert other.status_code == 404

    listing = await client.get("/api/v1/ai/agent/runs", headers=site_engineer_headers)
    assert listing.status_code == 200
    assert not any(item["id"] == run_id for item in listing.json()["items"])


async def test_oversight_roles_can_read_any_users_run(client, admin_headers, procurement_headers):
    created = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Give an executive overview of the portfolio"},
        headers=procurement_headers,
    )
    run_id = created.json()["id"]

    detail = await client.get(f"/api/v1/ai/agent/runs/{run_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id


async def test_owner_can_still_read_their_own_run(client, procurement_headers):
    created = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Give an executive overview of the portfolio"},
        headers=procurement_headers,
    )
    run_id = created.json()["id"]

    detail = await client.get(f"/api/v1/ai/agent/runs/{run_id}", headers=procurement_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id


async def test_conversation_id_cannot_be_hijacked_by_another_user(
    client, procurement_headers, site_engineer_headers
):
    # A user must never be able to continue someone else's conversation by supplying its id —
    # that would inherit the other user's project scope and history into their own answer.
    first = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Give an executive overview of the portfolio"},
        headers=procurement_headers,
    )
    conversation_id = first.json()["conversation_id"]

    hijack = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "what did we just discuss?", "conversation_id": conversation_id},
        headers=site_engineer_headers,
    )
    assert hijack.status_code == 200
    assert hijack.json()["conversation_id"] != conversation_id


async def test_admin_can_deprecate_and_reactivate_skill(client, admin_headers):
    await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skill_id = (await client.get("/api/v1/ai/agent/skills", headers=admin_headers)).json()[0]["id"]

    deprecated = await client.patch(
        f"/api/v1/ai/agent/skills/{skill_id}", json={"status": "deprecated"}, headers=admin_headers
    )
    assert deprecated.status_code == 200
    assert deprecated.json()["status"] == "deprecated"

    reactivated = await client.patch(
        f"/api/v1/ai/agent/skills/{skill_id}", json={"status": "active"}, headers=admin_headers
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"


async def test_non_admin_cannot_update_skill_status(client, admin_headers, procurement_headers):
    await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skill_id = (await client.get("/api/v1/ai/agent/skills", headers=admin_headers)).json()[0]["id"]

    response = await client.patch(
        f"/api/v1/ai/agent/skills/{skill_id}",
        json={"status": "deprecated"},
        headers=procurement_headers,
    )
    assert response.status_code == 403


async def test_update_missing_skill_status_404(client, admin_headers):
    response = await client.patch(
        "/api/v1/ai/agent/skills/999999", json={"status": "deprecated"}, headers=admin_headers
    )
    assert response.status_code == 404


async def test_deprecated_skill_is_excluded_from_reuse(client, admin_headers):
    first = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skill_id = (await client.get("/api/v1/ai/agent/skills", headers=admin_headers)).json()[0]["id"]
    await client.patch(
        f"/api/v1/ai/agent/skills/{skill_id}", json={"status": "deprecated"}, headers=admin_headers
    )

    second = await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 2"},
        headers=admin_headers,
    )
    assert second.status_code == 200
    # The deprecated skill must not be picked up by fresh planning, even though the same
    # near-identical phrasing reused it before it was deprecated.
    assert second.json()["skill_used"] != first.json()["skill_created"]


async def test_admin_can_delete_orphan_skill(client, admin_headers, db_session):
    orphan = AgentSkill(
        name="orphan-admin-delete-test",
        description="A skill with no run history, safe to hard-delete",
        trigger_keywords=["orphan", "delete", "test"],
        plan=[{"tool": "search_memory", "args": {"query": "$goal"}}],
        parameters=[],
        created_by="agent",
        status="active",
        usage_count=0,
        success_count=0,
        version=1,
    )
    db_session.add(orphan)
    await db_session.flush()
    await db_session.commit()

    response = await client.delete(f"/api/v1/ai/agent/skills/{orphan.id}", headers=admin_headers)
    assert response.status_code == 204

    missing = await client.get(f"/api/v1/ai/agent/skills/{orphan.id}", headers=admin_headers)
    assert missing.status_code == 404


async def test_deleting_skill_with_run_history_returns_409(client, admin_headers):
    # The FK constraint must surface as a clean 409 (the app-wide IntegrityError handler),
    # not a 500 — matching the same pattern every other entity's FK-blocked delete follows
    # (see test_delete_blocked_by_children_returns_409 in test_entity_edit_delete.py). No
    # follow-up request is made on this client afterward: the shared test session is left in
    # a rolled-back state after the FK violation, same as that existing test.
    await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skill_id = (await client.get("/api/v1/ai/agent/skills", headers=admin_headers)).json()[0]["id"]

    response = await client.delete(f"/api/v1/ai/agent/skills/{skill_id}", headers=admin_headers)
    assert response.status_code == 409


async def test_non_admin_cannot_delete_skill(client, admin_headers, procurement_headers):
    await client.post(
        "/api/v1/ai/agent/run",
        json={"goal": "Assess the risk of supplier 1"},
        headers=admin_headers,
    )
    skill_id = (await client.get("/api/v1/ai/agent/skills", headers=admin_headers)).json()[0]["id"]

    response = await client.delete(
        f"/api/v1/ai/agent/skills/{skill_id}", headers=procurement_headers
    )
    assert response.status_code == 403


async def test_delete_missing_skill_404(client, admin_headers):
    response = await client.delete("/api/v1/ai/agent/skills/999999", headers=admin_headers)
    assert response.status_code == 404
