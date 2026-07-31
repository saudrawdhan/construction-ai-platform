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


async def test_meeting_action_items_are_scoped_to_their_meeting(client, admin_headers):
    # This previously asserted an empty list, which only held because the table was never
    # seeded — it described a data gap rather than a requirement. What actually matters is that
    # the endpoint returns this meeting's own follow-ups and nobody else's.
    response = await client.get("/api/v1/meetings/1/action-items", headers=admin_headers)
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert all(item["meeting_id"] == 1 for item in items)


async def test_missing_meeting_404(client, admin_headers):
    response = await client.get("/api/v1/meetings/999999", headers=admin_headers)
    assert response.status_code == 404
