# Тесты для API логов (in-memory ring buffer)
import time

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


@pytest.mark.asyncio
async def test_get_logs_filters_by_timestamp_range(test_app):
    now = int(time.time())
    await _handle_log({
        "timestamp": now - 30,
        "data": {"source": "auth", "line": "old-entry", "file": "/var/log/auth.log"},
    })
    await _handle_log({
        "timestamp": now - 20,
        "data": {"source": "auth", "line": "in-range-entry", "file": "/var/log/auth.log"},
    })
    await _handle_log({
        "timestamp": now - 10,
        "data": {"source": "auth", "line": "new-entry", "file": "/var/log/auth.log"},
    })

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/logs?source=auth&from_ts={now - 25}&to_ts={now - 15}&limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert [entry["line"] for entry in data] == ["in-range-entry"]


@pytest.mark.asyncio
async def test_get_logs_filters_by_ip_and_search_query(test_app):
    now = int(time.time())
    await _handle_log({
        "timestamp": now - 20,
        "data": {"source": "auth", "line": "Failed password for root from 203.0.113.9 port 22 ssh2", "file": "/var/log/auth.log"},
    })
    await _handle_log({
        "timestamp": now - 10,
        "data": {"source": "auth", "line": "Accepted publickey for root from 198.51.100.7 port 22 ssh2", "file": "/var/log/auth.log"},
    })

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/logs?source=auth&ip=203.0.113.9&q=failed&limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "203.0.113.9" in data[0]["line"]


@pytest.mark.asyncio
async def test_get_logs_filters_by_event_type(test_app):
    now = int(time.time())
    await _handle_log({
        "timestamp": now - 30,
        "data": {"source": "nginx", "line": '10.0.0.5 - - "GET /index.html HTTP/1.1" 200', "file": "/var/log/nginx/access.log"},
    })
    await _handle_log({
        "timestamp": now - 20,
        "data": {"source": "nginx", "line": '10.0.0.5 - - "GET /../../etc/passwd HTTP/1.1" 200', "file": "/var/log/nginx/access.log"},
    })

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/logs?event_type=path_traversal&limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "../../etc/passwd" in data[0]["line"]
