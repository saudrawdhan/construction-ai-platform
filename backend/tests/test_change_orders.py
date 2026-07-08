async def test_list_change_orders_total(client, admin_headers):
    response = await client.get("/api/v1/change-orders?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 120


async def test_filter_change_orders_by_status(client, admin_headers):
    response = await client.get("/api/v1/change-orders?status=Approved", headers=admin_headers)
    assert response.status_code == 200
    assert all(c["status"] == "Approved" for c in response.json()["items"])


async def test_get_change_order(client, admin_headers):
    response = await client.get("/api/v1/change-orders/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["co_number"] == "CO-00001"


async def test_missing_change_order_404(client, admin_headers):
    response = await client.get("/api/v1/change-orders/999999", headers=admin_headers)
    assert response.status_code == 404
