async def test_list_meetings_total(client, admin_headers):
    response = await client.get("/api/v1/meetings?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 260


async def test_filter_meetings_by_type(client, admin_headers):
    response = await client.get("/api/v1/meetings?meeting_type=Safety", headers=admin_headers)
    assert response.status_code == 200
    assert all(m["meeting_type"] == "Safety" for m in response.json()["items"])


async def test_meeting_decisions(client, admin_headers):
    response = await client.get("/api/v1/meetings/1/decisions", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_meeting_action_items_empty_until_workflow(client, admin_headers):
    response = await client.get("/api/v1/meetings/1/action-items", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_missing_meeting_404(client, admin_headers):
    response = await client.get("/api/v1/meetings/999999", headers=admin_headers)
    assert response.status_code == 404
