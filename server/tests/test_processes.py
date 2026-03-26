# Тесты для API процессов (in-memory хранилище)
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_get_processes_returns_list(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/processes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
