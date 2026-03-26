# Тесты для API логов (in-memory ring buffer)
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_get_logs_returns_list(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/logs?source=auth&limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
