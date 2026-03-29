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
async def test_get_security_events_with_source_ip_filter(test_app):
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
        (now, "ssh_brute_force", "high", "10.0.0.2", "5 failed attempts")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?event_type=ssh_brute_force&source_ip=10.0.0.2")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source_ip"] == "10.0.0.2"

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
async def test_get_security_events_enriches_web_login_abuse_signal(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now, "web_login_bruteforce", "high", "10.0.0.55", "5+ repeated web login attempts in 300s", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?event_type=web_login_bruteforce")
    data = resp.json()
    assert data[0]["signal_source"] == "rule_web_logs"
    assert data[0]["explanation_code"] == "web_login_threshold"
    assert data[0]["confidence"] == "high"

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
    assert incident["latest_action_taken"] == "auto_block"
    assert incident["evidence_types"] == ["ssh_brute_force"]


@pytest.mark.asyncio
async def test_get_security_incidents_includes_repeat_and_suppressed_counts(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 30, "port_scan", "medium", "10.0.0.21", "12 unique destination ports probed in 120s", "auto_block")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 10, "port_scan", "medium", "10.0.0.21", "12 unique destination ports probed in 120s", "review_required")
    )
    await conn.execute(
        "INSERT INTO response_audit (timestamp, trace_id, stage, status, event_type, source_ip, action, command, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now - 5, "trace-suppressed", "decision", "suppressed", "port_scan", "10.0.0.21", "review_required", "", '{"reason":"already_blocked_followup"}')
    )
    await conn.execute(
        "INSERT INTO response_audit (timestamp, trace_id, stage, status, event_type, source_ip, action, command, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now - 4, "trace-duplicate", "decision", "suppressed_duplicate", "port_scan", "10.0.0.21", "review_required", "", '{"reason":"recent_duplicate_event"}')
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents?event_type=port_scan")
    data = resp.json()
    incident = next(item for item in data if item["type"] == "port_scan" and item["source_ip"] == "10.0.0.21")
    assert incident["event_count"] == 2
    assert incident["suppressed_count"] == 1
    assert incident["repeat_count"] == 3


@pytest.mark.asyncio
async def test_get_security_incidents_builds_correlated_recon_chain(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 20, "scanner_probe", "medium", "10.0.0.44", "scanner_probe pattern detected", "review_required")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 10, "sensitive_path_probe", "medium", "10.0.0.44", "sensitive_path_probe pattern detected", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents")
    data = resp.json()
    incident = next(item for item in data if item["type"] == "recon_chain" and item["source_ip"] == "10.0.0.44")
    assert incident["event_count"] == 2
    assert incident["severity"] == "medium"
    assert incident["confidence"] == "medium"
    assert incident["recommended_action"] == "review_source_ip"
    assert incident["evidence_types"] == ["scanner_probe", "sensitive_path_probe"]


@pytest.mark.asyncio
async def test_get_security_incidents_builds_credential_attack_chain(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 40, "ssh_user_enum", "medium", "10.0.0.88", "3+ invalid SSH users in 60s", "review_required")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 10, "ssh_brute_force", "high", "10.0.0.88", "5+ failed SSH attempts in 60s", "auto_block")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents")
    data = resp.json()
    incident = next(item for item in data if item["type"] == "credential_attack_chain" and item["source_ip"] == "10.0.0.88")
    assert incident["severity"] == "critical"
    assert incident["confidence"] == "high"
    assert incident["recommended_action"] == "auto_block_applied"
    assert incident["evidence_types"] == ["ssh_user_enum", "ssh_brute_force"]


@pytest.mark.asyncio
async def test_get_security_incidents_builds_web_attack_chain(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 30, "scanner_probe", "medium", "10.0.0.91", "scanner_probe pattern detected", "review_required")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 15, "path_traversal", "medium", "10.0.0.91", "path_traversal pattern detected", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents")
    data = resp.json()
    incident = next(item for item in data if item["type"] == "web_attack_chain" and item["source_ip"] == "10.0.0.91")
    assert incident["severity"] == "high"
    assert incident["evidence_types"] == ["scanner_probe", "path_traversal"]


@pytest.mark.asyncio
async def test_get_security_incidents_builds_web_attack_chain_for_command_injection(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 30, "scanner_probe", "medium", "10.0.0.92", "scanner_probe pattern detected", "review_required")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 10, "command_injection", "high", "10.0.0.92", "command_injection pattern detected", "auto_block")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents")
    data = resp.json()
    incident = next(item for item in data if item["type"] == "web_attack_chain" and item["source_ip"] == "10.0.0.92")
    assert incident["recommended_action"] == "auto_block_applied"
    assert "command_injection" in incident["evidence_types"]


@pytest.mark.asyncio
async def test_update_incident_status_persists_and_marks_events_resolved(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken, resolved) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (now - 30, "ssh_brute_force", "high", "10.0.0.55", "5 failed attempts", "review_required", 0)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        update = await client.post("/api/security/incidents/ssh_brute_force%3A10.0.0.55/status", json={"status": "resolved"})
        incidents = await client.get("/api/security/incidents")

    assert update.status_code == 200
    incident = next(item for item in incidents.json() if item["id"] == "ssh_brute_force:10.0.0.55")
    assert incident["status"] == "resolved"
    assert incident["status_updated_at"] > 0

    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT resolved FROM security_events WHERE type = ? AND source_ip = ?",
            ("ssh_brute_force", "10.0.0.55"),
        )
        row = await cursor.fetchone()
    finally:
        await conn.close()
    assert int(row["resolved"]) == 1


@pytest.mark.asyncio
async def test_incident_notes_roundtrip_and_note_count(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now - 20, "port_scan", "medium", "10.0.0.77", "12 unique destination ports probed in 120s", "review_required")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        note_resp = await client.post(
            "/api/security/incidents/port_scan%3A10.0.0.77/notes",
            json={"note": "Проверили firewall-логи, подтверждаем разведку."},
        )
        notes_resp = await client.get("/api/security/incidents/port_scan%3A10.0.0.77/notes")
        incidents_resp = await client.get("/api/security/incidents?event_type=port_scan")

    assert note_resp.status_code == 200
    notes = notes_resp.json()
    assert len(notes) == 1
    assert notes[0]["note"] == "Проверили firewall-логи, подтверждаем разведку."
    assert notes[0]["status_at_time"] == "new"

    incident = next(item for item in incidents_resp.json() if item["id"] == "port_scan:10.0.0.77")
    assert incident["note_count"] == 1


@pytest.mark.asyncio
async def test_get_security_incident_detail_returns_evidence_and_resolution(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken, trace_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (now - 40, "ssh_user_enum", "medium", "10.0.0.81", "3+ invalid SSH users in 60s", "review_required", "trace-detail-1")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken, trace_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (now - 10, "ssh_brute_force", "high", "10.0.0.81", "Rule+ML confirmed: ssh_brute_force", "auto_block", "trace-detail-1")
    )
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) VALUES (?, ?, ?, ?, ?)",
        ("10.0.0.81", "Rule+ML confirmed: ssh_brute_force", now - 10, now + 3600, 1),
    )
    await conn.execute(
        "INSERT INTO incident_state (incident_id, status, updated_at) VALUES (?, ?, ?)",
        ("credential_attack_chain:10.0.0.81", "investigating", now - 5),
    )
    await conn.execute(
        "INSERT INTO incident_notes (incident_id, incident_type, source_ip, note, status_at_time, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("credential_attack_chain:10.0.0.81", "credential_attack_chain", "10.0.0.81", "Проверили, блокировка уже применена.", "investigating", now - 4),
    )
    await conn.execute(
        "INSERT INTO response_audit (timestamp, trace_id, stage, status, event_type, source_ip, action, command, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now - 9, "trace-detail-1", "decision", "block", "ssh_brute_force", "10.0.0.81", "auto_block", "", '{"policy_stage":"block","reason":"credential_attack_first_seen"}')
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/incidents/credential_attack_chain%3A10.0.0.81")

    assert resp.status_code == 200
    data = resp.json()
    assert data["incident"]["id"] == "credential_attack_chain:10.0.0.81"
    assert len(data["related_events"]) == 2
    assert data["blocked_ip"]["ip"] == "10.0.0.81"
    assert data["resolution_summary"]["state"] == "contained"
    assert len(data["audit_entries"]) == 1
    assert data["evidence_summary"][0]["count"] >= 1
    assert len(data["progression"]) == 2


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
async def test_get_security_mode_defaults(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/mode")
    assert resp.status_code == 200
    assert resp.json()["operation_mode"] == "auto_defend"


@pytest.mark.asyncio
async def test_update_security_mode_persists_runtime_state(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/mode", json={"operation_mode": "assist"})
        assert resp.status_code == 200
        follow_up = await client.get("/api/security/mode")
    assert resp.json()["operation_mode"] == "assist"
    assert follow_up.json()["operation_mode"] == "assist"

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


@pytest.mark.asyncio
async def test_block_ip_rejects_on_standby(standby_test_app):
    transport = ASGITransport(app=standby_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": "10.0.0.9",
            "reason": "manual block",
            "duration": 3600
        })
    assert resp.status_code == 409
