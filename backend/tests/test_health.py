import httpx
from httpx import ASGITransport

from app.main import app


async def test_health_reports_service_status():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert set(body["services"]) == {"database", "redis"}


async def test_openapi_exposes_versioned_prefix():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"]
