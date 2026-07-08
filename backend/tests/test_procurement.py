async def test_list_suppliers(client, admin_headers):
    response = await client.get("/api/v1/suppliers?size=10", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 80
    assert len(body["items"]) == 10


async def test_supplier_performance_shape(client, admin_headers):
    response = await client.get("/api/v1/suppliers/1/performance", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["supplier_id"] == 1
    assert body["total_purchase_orders"] >= body["late_purchase_orders"]
    assert 0.0 <= body["on_time_rate"] <= 100.0
    assert isinstance(body["top_delay_causes"], list)


async def test_supplier_performance_missing_returns_404(client, admin_headers):
    response = await client.get("/api/v1/suppliers/999999/performance", headers=admin_headers)
    assert response.status_code == 404


async def test_list_purchase_requests_total(client, admin_headers):
    url = "/api/v1/procurement/purchase-requests?size=1"
    response = await client.get(url, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 3000


async def test_incomplete_purchase_requests_filter(client, admin_headers):
    full = await client.get(
        "/api/v1/procurement/purchase-requests?size=1", headers=admin_headers
    )
    incomplete = await client.get(
        "/api/v1/procurement/purchase-requests?size=1&incomplete=true", headers=admin_headers
    )
    assert incomplete.json()["total"] < full.json()["total"]
    assert incomplete.json()["total"] > 0


async def test_late_purchase_orders_filter(client, admin_headers):
    response = await client.get(
        "/api/v1/procurement/purchase-orders?is_late=true&size=1", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 714


async def test_purchase_order_requires_auth(client):
    response = await client.get("/api/v1/procurement/purchase-orders")
    assert response.status_code == 401
