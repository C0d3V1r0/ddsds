import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_returns_status(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "agent" in data
    assert "db" in data
