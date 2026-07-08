async def test_list_rfis_total(client, admin_headers):
    response = await client.get("/api/v1/rfis?size=1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 294


async def test_overdue_rfis_filter(client, admin_headers):
    response = await client.get("/api/v1/rfis?overdue=true&size=5", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 172
    assert all(item["status"] != "Closed" for item in body["items"])


async def test_get_rfi_by_id(client, admin_headers):
    response = await client.get("/api/v1/rfis/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == 1


async def test_get_missing_rfi_returns_404(client, admin_headers):
    response = await client.get("/api/v1/rfis/999999", headers=admin_headers)
    assert response.status_code == 404
