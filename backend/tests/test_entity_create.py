"""Direct create endpoints for the operational entities (so a company can enter its own data)."""


async def test_create_rfi(client, admin_headers):
    payload = {
        "project_id": 1,
        "rfi_number": "RFI-TEST-1",
        "subject": "Clarify rebar spacing",
        "question": "What is the required spacing on grid C?",
        "discipline": "Structural",
        "raised_by": "Main Contractor",
        "assigned_to": "Design Consultant",
        "priority": "High",
    }
    response = await client.post("/api/v1/rfis", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rfi_number"] == "RFI-TEST-1"
    assert body["status"] == "Open"  # default applied


async def test_create_change_order(client, admin_headers):
    payload = {
        "project_id": 1,
        "co_number": "CO-TEST-1",
        "description": "Additional excavation for rock",
        "value": "150000.00",
    }
    response = await client.post("/api/v1/change-orders", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "Pending"


async def test_create_claim(client, admin_headers):
    payload = {
        "project_id": 1,
        "claim_number": "CLM-TEST-1",
        "claim_type": "Cost",
        "amount": "500000.00",
        "narrative": "Prolongation costs due to late access.",
    }
    response = await client.post("/api/v1/claims", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "Submitted"


async def test_create_meeting(client, admin_headers):
    payload = {
        "project_id": 1,
        "title": "Project Kickoff",
        "meeting_type": "General",
        "meeting_date": "2026-02-01",
    }
    response = await client.post("/api/v1/meetings", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["title"] == "Project Kickoff"


async def test_create_site_report(client, admin_headers):
    payload = {
        "project_id": 1,
        "weather": "Clear",
        "summary": "Poured the ground-floor slab on grid A-C.",
        "report_date": "2026-02-02",
    }
    response = await client.post("/api/v1/site-reports", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["weather"] == "Clear"


async def test_create_purchase_request(client, admin_headers):
    payload = {
        "project_id": 1,
        "request_no": "PR-TEST-1",
        "material_category": "Steel",
        "specification": "Reinforcement bar 16mm",
    }
    response = await client.post(
        "/api/v1/procurement/purchase-requests", headers=admin_headers, json=payload
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "Under Review"


async def test_create_purchase_order_computes_lateness(client, admin_headers):
    payload = {
        "pr_id": 1,
        "project_id": 1,
        "supplier_id": 1,
        "po_number": "PO-TEST-1",
        "promised_delivery": "2026-01-01",
        "actual_delivery": "2026-01-11",
    }
    response = await client.post(
        "/api/v1/procurement/purchase-orders", headers=admin_headers, json=payload
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_late"] is True
    assert body["delay_days"] == 10


async def test_create_purchase_order_on_time(client, admin_headers):
    payload = {
        "pr_id": 1,
        "project_id": 1,
        "supplier_id": 1,
        "po_number": "PO-TEST-2",
        "promised_delivery": "2026-01-10",
        "actual_delivery": "2026-01-08",
    }
    response = await client.post(
        "/api/v1/procurement/purchase-orders", headers=admin_headers, json=payload
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_late"] is False
    assert body["delay_days"] == 0


async def test_viewer_cannot_create_rfi(client, viewer_headers):
    response = await client.post(
        "/api/v1/rfis",
        headers=viewer_headers,
        json={
            "project_id": 1,
            "rfi_number": "X",
            "subject": "x",
            "question": "x",
            "discipline": "x",
            "raised_by": "x",
            "assigned_to": "x",
        },
    )
    assert response.status_code == 403


async def test_viewer_cannot_create_claim(client, viewer_headers):
    response = await client.post(
        "/api/v1/claims",
        headers=viewer_headers,
        json={
            "project_id": 1,
            "claim_number": "X",
            "claim_type": "Cost",
            "amount": "1",
            "narrative": "x",
        },
    )
    assert response.status_code == 403
