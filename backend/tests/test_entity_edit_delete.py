"""Edit (PATCH) and delete (DELETE) for the operational entities a company manages itself.

Each entity is created inside the test's rolled-back transaction, then updated and deleted, so no
foreign-key children exist to block the delete. Delete-blocked-by-children and the auth guards are
covered by dedicated cases.
"""


async def _create_rfi(client, headers) -> int:
    payload = {
        "project_id": 1,
        "rfi_number": "RFI-ED-1",
        "subject": "Original subject",
        "question": "Original question",
        "discipline": "Structural",
        "raised_by": "Contractor",
        "assigned_to": "Consultant",
    }
    return (await client.post("/api/v1/rfis", headers=headers, json=payload)).json()["id"]


async def test_update_rfi(client, admin_headers):
    rfi_id = await _create_rfi(client, admin_headers)
    response = await client.patch(
        f"/api/v1/rfis/{rfi_id}",
        headers=admin_headers,
        json={"subject": "Revised subject", "status": "Closed"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subject"] == "Revised subject"
    assert body["status"] == "Closed"
    assert body["question"] == "Original question"  # untouched fields preserved


async def test_delete_rfi(client, admin_headers):
    rfi_id = await _create_rfi(client, admin_headers)
    response = await client.delete(f"/api/v1/rfis/{rfi_id}", headers=admin_headers)
    assert response.status_code == 204
    assert (await client.get(f"/api/v1/rfis/{rfi_id}", headers=admin_headers)).status_code == 404


async def test_update_and_delete_claim(client, admin_headers):
    claim_id = (
        await client.post(
            "/api/v1/claims",
            headers=admin_headers,
            json={
                "project_id": 1,
                "claim_number": "CLM-ED-1",
                "claim_type": "Cost",
                "amount": "100000.00",
                "narrative": "Original narrative.",
            },
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/claims/{claim_id}",
        headers=admin_headers,
        json={"status": "Under Review", "amount": "250000.00"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "Under Review"
    assert updated.json()["amount"] == "250000.00"

    deleted = await client.delete(f"/api/v1/claims/{claim_id}", headers=admin_headers)
    assert deleted.status_code == 204


async def test_update_and_delete_change_order(client, admin_headers):
    co_id = (
        await client.post(
            "/api/v1/change-orders",
            headers=admin_headers,
            json={
                "project_id": 1,
                "co_number": "CO-ED-1",
                "description": "Original scope",
                "value": "50000.00",
            },
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/change-orders/{co_id}",
        headers=admin_headers,
        json={"status": "Approved", "value": "75000.00"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "Approved"
    assert updated.json()["value"] == "75000.00"

    assert (
        await client.delete(f"/api/v1/change-orders/{co_id}", headers=admin_headers)
    ).status_code == 204


async def test_update_and_delete_meeting(client, admin_headers):
    meeting_id = (
        await client.post(
            "/api/v1/meetings",
            headers=admin_headers,
            json={"project_id": 1, "title": "Draft title", "meeting_type": "General"},
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/meetings/{meeting_id}",
        headers=admin_headers,
        json={"title": "Final title"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Final title"

    assert (
        await client.delete(f"/api/v1/meetings/{meeting_id}", headers=admin_headers)
    ).status_code == 204


async def test_update_and_delete_site_report(client, admin_headers):
    report_id = (
        await client.post(
            "/api/v1/site-reports",
            headers=admin_headers,
            json={"project_id": 1, "weather": "Clear", "summary": "Initial summary."},
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/site-reports/{report_id}",
        headers=admin_headers,
        json={"weather": "Dusty", "summary": "Corrected summary."},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["weather"] == "Dusty"

    assert (
        await client.delete(f"/api/v1/site-reports/{report_id}", headers=admin_headers)
    ).status_code == 204


async def test_update_and_delete_purchase_request(client, admin_headers):
    pr_id = (
        await client.post(
            "/api/v1/procurement/purchase-requests",
            headers=admin_headers,
            json={"project_id": 1, "request_no": "PR-ED-1", "material_category": "Steel"},
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/procurement/purchase-requests/{pr_id}",
        headers=admin_headers,
        json={"status": "Approved", "material_category": "Concrete"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "Approved"
    assert updated.json()["material_category"] == "Concrete"

    assert (
        await client.delete(
            f"/api/v1/procurement/purchase-requests/{pr_id}", headers=admin_headers
        )
    ).status_code == 204


async def test_update_and_delete_supplier(client, admin_headers):
    supplier_id = (
        await client.post(
            "/api/v1/suppliers",
            headers=admin_headers,
            json={"supplier_name": "Edit Co", "category": "Steel", "city": "Riyadh"},
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/suppliers/{supplier_id}",
        headers=admin_headers,
        json={"status": "Inactive"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "Inactive"

    assert (
        await client.delete(f"/api/v1/suppliers/{supplier_id}", headers=admin_headers)
    ).status_code == 204


async def test_update_and_delete_project(client, admin_headers):
    project_id = (
        await client.post(
            "/api/v1/projects",
            headers=admin_headers,
            json={
                "project_code": "PRJ-ED-1",
                "project_name": "Editable Project",
                "project_type": "Tower",
                "client_name": "New Client Co",
                "city": "Riyadh",
                "status": "Active",
                "budget": "1000000",
            },
        )
    ).json()["id"]

    updated = await client.patch(
        f"/api/v1/projects/{project_id}",
        headers=admin_headers,
        json={"status": "On Hold", "budget": "2000000"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "On Hold"
    assert updated.json()["budget"] == "2000000.00"

    assert (
        await client.delete(f"/api/v1/projects/{project_id}", headers=admin_headers)
    ).status_code == 204


async def test_update_purchase_order_recomputes_lateness(client, admin_headers):
    created = await client.post(
        "/api/v1/procurement/purchase-orders",
        headers=admin_headers,
        json={
            "pr_id": 1,
            "project_id": 1,
            "supplier_id": 1,
            "po_number": "PO-ED-1",
            "promised_delivery": "2026-01-10",
            "actual_delivery": "2026-01-08",
        },
    )
    po = created.json()
    assert po["is_late"] is False

    # Push the actual delivery past the promised date -> the service must recompute lateness.
    updated = await client.patch(
        f"/api/v1/procurement/purchase-orders/{po['id']}",
        headers=admin_headers,
        json={"actual_delivery": "2026-01-25"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["is_late"] is True
    assert body["delay_days"] == 15

    deleted = await client.delete(
        f"/api/v1/procurement/purchase-orders/{po['id']}", headers=admin_headers
    )
    assert deleted.status_code == 204


async def test_delete_blocked_by_children_returns_409(client, admin_headers):
    # Project 1 is seeded with dependent records (purchase requests, RFIs, …); the FK constraint
    # must surface as a clean 409, not a 500.
    response = await client.delete("/api/v1/projects/1", headers=admin_headers)
    assert response.status_code == 409


async def test_update_missing_entity_returns_404(client, admin_headers):
    response = await client.patch(
        "/api/v1/rfis/999999", headers=admin_headers, json={"status": "Closed"}
    )
    assert response.status_code == 404


async def test_viewer_cannot_update(client, viewer_headers):
    response = await client.patch(
        "/api/v1/rfis/1", headers=viewer_headers, json={"status": "Closed"}
    )
    assert response.status_code == 403


async def test_viewer_cannot_delete(client, viewer_headers):
    response = await client.delete("/api/v1/claims/1", headers=viewer_headers)
    assert response.status_code == 403
