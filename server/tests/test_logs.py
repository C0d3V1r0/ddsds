# Тесты для API логов (in-memory ring buffer)
import pytest
from httpx import AsyncClient, ASGITransport
from ws.agent import _handle_log


@pytest.mark.asyncio
async def test_get_logs_returns_list(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/logs?source=auth&limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_log_entries_are_truncated_before_buffering(test_app):
    await _handle_log({
        "timestamp": 1_700_000_000,
        "data": {
            "source": "n" * 100,
            "line": "x" * 5000,
            "file": "/var/log/" + ("a" * 1000),
        },
    })

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/logs?limit=1")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data[0]["source"]) == 64
    assert len(data[0]["line"]) == 4096
    assert len(data[0]["file"]) == 512
