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
    assert data[0]["signal_source"] == "rule_auth_logs"
    assert data[0]["explanation_code"] == "ssh_failed_attempts_threshold"
    assert data[0]["confidence"] == "high"
    assert data[0]["recommended_action"] == "review_source_ip"

@pytest.mark.asyncio
async def test_get_security_events_enriches_ml_detection(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now, "ssh_brute_force", "low", "", "ML-detected: ssh_brute_force", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?event_type=ssh_brute_force")
    data = resp.json()
    assert any(item["signal_source"] == "ml_log_classifier" for item in data)


@pytest.mark.asyncio
async def test_get_security_events_enriches_rule_plus_ml_detection(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now, "path_traversal", "high", "10.0.0.12", "Rule+ML confirmed: path_traversal", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?event_type=path_traversal")
    data = resp.json()
    assert data[0]["signal_source"] == "rule_plus_ml"
    assert data[0]["explanation_code"] == "rule_ml_confirmed"
    assert data[0]["confidence"] == "high"


@pytest.mark.asyncio
async def test_get_security_events_enriches_port_scan_signal(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now, "port_scan", "medium", "10.0.0.33", "12 unique destination ports probed in 120s", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?event_type=port_scan")
    data = resp.json()
    assert data[0]["signal_source"] == "rule_firewall_logs"
    assert data[0]["explanation_code"] == "unique_destination_ports_threshold"
    assert data[0]["recommended_action"] == "review_source_ip"

@pytest.mark.asyncio
async def test_get_security_incidents_groups_related_events(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 30, "ssh_brute_force", "high", "10.0.0.7", "5 failed attempts", "auto_block")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 10, "ssh_brute_force", "high", "10.0.0.7", "5 failed attempts", "auto_block")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents")
    data = resp.json()
    incident = next(item for item in data if item["type"] == "ssh_brute_force" and item["source_ip"] == "10.0.0.7")
    assert incident["event_count"] >= 2
    assert incident["status"] == "new"
    assert "latest_trace_id" in incident


@pytest.mark.asyncio
async def test_get_response_audit_filters_by_trace_id(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO response_audit (timestamp, trace_id, stage, status, event_type, source_ip, action, command, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now, "trace-1", "decision", "review", "port_scan", "10.0.0.9", "review_required", "", '{"policy_action":"review"}')
    )
    await conn.execute(
        "INSERT INTO response_audit (timestamp, trace_id, stage, status, event_type, source_ip, action, command, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now, "trace-2", "command_result", "success", "ssh_brute_force", "10.0.0.7", "auto_block", "block_ip", '{"origin":"auto_response"}')
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/audit?trace_id=trace-2")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["trace_id"] == "trace-2"
    assert data[0]["command"] == "block_ip"
    assert data[0]["details"]["origin"] == "auto_response"

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
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_block_ip_rejects_invalid_duration(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": "10.0.0.5",
            "reason": "manual block",
            "duration": -1
        })
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_block_ip_strips_ip_and_reason(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": " 10.0.0.8 ",
            "reason": "  manual block  ",
            "duration": 3600
        })
    assert resp.status_code == 200
    assert resp.json()["ip"] == "10.0.0.8"

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

@pytest.mark.asyncio
async def test_unblock_ip_invalid_format(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/unblock", json={"ip": "bad ip"})
    assert resp.status_code == 422
