async def test_list_site_reports_total(client, admin_headers):
    response = await client.get("/api/v1/site-reports?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1200


async def test_filter_site_reports_by_project(client, admin_headers):
    response = await client.get("/api/v1/site-reports?project_id=14", headers=admin_headers)
    assert response.status_code == 200
    assert all(r["project_id"] == 14 for r in response.json()["items"])


async def test_site_report_activities(client, admin_headers):
    response = await client.get("/api/v1/site-reports/1/activities", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_missing_site_report_404(client, admin_headers):
    response = await client.get("/api/v1/site-reports/999999", headers=admin_headers)
    assert response.status_code == 404
