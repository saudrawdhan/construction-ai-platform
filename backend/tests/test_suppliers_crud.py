async def test_create_supplier(client, admin_headers):
    payload = {
        "supplier_name": "New Test Supplier",
        "category": "Steel",
        "city": "Riyadh",
        "status": "Active",
    }
    response = await client.post("/api/v1/suppliers", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["supplier_name"] == "New Test Supplier"

    fetched = await client.get(f"/api/v1/suppliers/{body['id']}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["city"] == "Riyadh"


async def test_create_supplier_defaults_status_active(client, admin_headers):
    payload = {"supplier_name": "No Status Supplier", "category": "Concrete", "city": "Dammam"}
    response = await client.post("/api/v1/suppliers", headers=admin_headers, json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "Active"


async def test_update_supplier_partial(client, admin_headers):
    created = (
        await client.post(
            "/api/v1/suppliers",
            headers=admin_headers,
            json={"supplier_name": "Edit Me", "category": "Concrete", "city": "Dammam"},
        )
    ).json()

    response = await client.patch(
        f"/api/v1/suppliers/{created['id']}",
        headers=admin_headers,
        json={"status": "Inactive", "city": "Jeddah"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Inactive"
    assert body["city"] == "Jeddah"
    assert body["supplier_name"] == "Edit Me"  # untouched fields are preserved


async def test_update_missing_supplier_returns_404(client, admin_headers):
    response = await client.patch(
        "/api/v1/suppliers/999999", headers=admin_headers, json={"city": "Nowhere"}
    )
    assert response.status_code == 404


async def test_viewer_cannot_create_supplier(client, viewer_headers):
    response = await client.post(
        "/api/v1/suppliers",
        headers=viewer_headers,
        json={"supplier_name": "Blocked", "category": "Steel", "city": "Riyadh"},
    )
    assert response.status_code == 403
