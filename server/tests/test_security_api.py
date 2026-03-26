# server/tests/test_security_api.py
import pytest
import time
from httpx import AsyncClient, ASGITransport
from db import get_db

@pytest.mark.asyncio
async def test_get_security_events_empty(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_get_security_events_with_filter(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, "ssh_brute_force", "high", "10.0.0.1", "5 failed attempts")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, "sqli", "medium", "10.0.0.2", "SQL injection attempt")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?event_type=ssh_brute_force")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "ssh_brute_force"

@pytest.mark.asyncio
async def test_get_blocked_ips(test_app):
    conn = await get_db()
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) VALUES (?, ?, ?, ?)",
        ("192.168.1.100", "brute force", int(time.time()), 1)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/blocked")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ip"] == "192.168.1.100"

@pytest.mark.asyncio
async def test_block_ip_valid(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": "10.0.0.5",
            "reason": "manual block",
            "duration": 3600
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"

@pytest.mark.asyncio
async def test_block_ip_invalid_format(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": "not-an-ip",
            "reason": "test"
        })
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_unblock_ip(test_app):
    conn = await get_db()
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) VALUES (?, ?, ?, ?)",
        ("10.0.0.6", "test", int(time.time()), 0)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/unblock", json={"ip": "10.0.0.6"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "unblocked"
