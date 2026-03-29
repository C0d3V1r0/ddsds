# Тесты WebSocket-обработчика агента: auth, ping, отклонение без auth
import asyncio

import pytest
from starlette.testclient import TestClient
from tests.conftest import TEST_AGENT_SECRET
from deployment import init_deployment_role
from db import get_db
from ws.agent import _handle_log


@pytest.mark.asyncio
async def test_agent_ws_rejects_without_auth(test_app):
    # Без корректной аутентификации сервер отвечает auth_error и закрывает соединение
    client = TestClient(test_app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "wrong-secret"})
        resp = ws.receive_json()
        assert resp["type"] == "auth_error"
    # Соединение закрыто сервером после auth_error


@pytest.mark.asyncio
async def test_agent_ws_accepts_with_auth(test_app):
    # С корректным секретом агент получает auth_ok
    client = TestClient(test_app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": TEST_AGENT_SECRET})
        resp = ws.receive_json()
        assert resp["type"] == "auth_ok"


@pytest.mark.asyncio
async def test_agent_ws_handles_ping(test_app):
    # После аутентификации ping должен вернуть pong
    client = TestClient(test_app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": TEST_AGENT_SECRET})
        ws.receive_json()
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"


@pytest.mark.asyncio
async def test_agent_ws_records_command_result_audit(test_app):
    from db import start_writer, stop_writer
    import db as db_module

    writer_task = await start_writer(db_module._db_path)
    client = TestClient(test_app)
    try:
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"type": "auth", "secret": TEST_AGENT_SECRET})
            ws.receive_json()
            ws.send_json({
                "type": "command_result",
                "id": "cmd-1",
                "command": "block_ip",
                "params": {
                    "ip": "10.0.0.9",
                    "_meta": {
                        "trace_id": "trace-ws-1",
                        "event_type": "port_scan",
                        "source_ip": "10.0.0.9",
                        "action": "auto_block",
                        "origin": "auto_response",
                    },
                },
                "status": "success",
                "error": "",
            })
        await asyncio.sleep(0.05)
    finally:
        await stop_writer(writer_task)

    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT trace_id, command FROM agent_commands WHERE trace_id = ?", ("trace-ws-1",))
        command_row = await cursor.fetchone()
        cursor = await conn.execute(
            "SELECT trace_id, stage, status, command FROM response_audit WHERE trace_id = ? ORDER BY id DESC",
            ("trace-ws-1",),
        )
        audit_row = await cursor.fetchone()
    finally:
        await conn.close()

    assert command_row["trace_id"] == "trace-ws-1"
    assert command_row["command"] == "block_ip"
    assert audit_row["trace_id"] == "trace-ws-1"
    assert audit_row["stage"] == "command_result"
    assert audit_row["status"] == "success"
    assert audit_row["command"] == "block_ip"


@pytest.mark.asyncio
async def test_handle_log_suppresses_followup_port_scan_for_blocked_ip(test_app):
    now = 1_800_000_000

    async def direct_enqueue(sql: str, params: tuple[object, ...] = ()):
        conn = await get_db()
        try:
            await conn.execute(sql, params)
            await conn.commit()
        finally:
            await conn.close()

    async def noop_broadcast(_event: dict):
        return None

    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) VALUES (?, ?, ?, ?, ?)",
            ("10.0.0.22", "existing block", now - 30, now + 3600, 1),
        )
        await conn.commit()
    finally:
        await conn.close()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("ws.agent.enqueue_write", direct_enqueue)
    monkeypatch.setattr("security.audit.enqueue_write", direct_enqueue)
    monkeypatch.setattr("ws.frontend.broadcast", noop_broadcast)

    for port in (21, 22, 23, 25):
        await _handle_log({
            "timestamp": now + port,
            "data": {
                "source": "firewall",
                "line": f"kernel: NULLIUS_PORTSCAN IN=eth0 OUT= SRC=10.0.0.22 DST=10.0.0.2 PROTO=TCP SPT=50000 DPT={port}",
                "file": "/var/log/kern.log",
            },
        })
    await asyncio.sleep(0.05)
    monkeypatch.undo()

    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT COUNT(*) FROM security_events WHERE type = 'port_scan' AND source_ip = ?", ("10.0.0.22",))
        events_count = int((await cursor.fetchone())[0])
        cursor = await conn.execute(
            "SELECT status FROM response_audit WHERE source_ip = ? AND event_type = 'port_scan' ORDER BY id DESC LIMIT 1",
            ("10.0.0.22",),
        )
        audit_row = await cursor.fetchone()
    finally:
        await conn.close()

    assert events_count == 0
    assert audit_row["status"] == "suppressed"


@pytest.mark.asyncio
async def test_handle_log_suppresses_recent_duplicate_event(test_app):
    now = 1_800_000_200

    async def direct_enqueue(sql: str, params: tuple[object, ...] = ()):
        conn = await get_db()
        try:
            await conn.execute(sql, params)
            await conn.commit()
        finally:
            await conn.close()

    async def noop_broadcast(_event: dict):
        return None

    class StubDetector:
        def check_log(self, _log_entry: dict) -> dict:
            return {
                "type": "path_traversal",
                "severity": "medium",
                "source_ip": "10.0.0.44",
                "description": "path_traversal pattern detected",
                "raw_log": "raw",
            }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("ws.agent.enqueue_write", direct_enqueue)
    monkeypatch.setattr("security.audit.enqueue_write", direct_enqueue)
    monkeypatch.setattr("ws.frontend.broadcast", noop_broadcast)
    monkeypatch.setattr("ws.agent._detector", StubDetector())

    await _handle_log({
        "timestamp": now,
        "data": {
            "source": "nginx",
            "line": "10.0.0.44 - - \"GET /../../etc/passwd\"",
            "file": "/var/log/nginx/access.log",
        },
    })
    await _handle_log({
        "timestamp": now + 30,
        "data": {
            "source": "nginx",
            "line": "10.0.0.44 - - \"GET /../../etc/passwd\"",
            "file": "/var/log/nginx/access.log",
        },
    })
    await asyncio.sleep(0.05)
    monkeypatch.undo()

    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM security_events WHERE type = 'path_traversal' AND source_ip = ?",
            ("10.0.0.44",),
        )
        events_count = int((await cursor.fetchone())[0])
        cursor = await conn.execute(
            "SELECT status FROM response_audit WHERE source_ip = ? AND event_type = 'path_traversal' ORDER BY id DESC LIMIT 1",
            ("10.0.0.44",),
        )
        audit_row = await cursor.fetchone()
    finally:
        await conn.close()

    assert events_count == 1
    assert audit_row["status"] == "suppressed_duplicate"


@pytest.mark.asyncio
async def test_handle_log_downgrades_active_response_on_standby(test_app):
    now = 1_800_000_300

    async def direct_enqueue(sql: str, params: tuple[object, ...] = ()):
        conn = await get_db()
        try:
            await conn.execute(sql, params)
            await conn.commit()
        finally:
            await conn.close()

    async def noop_broadcast(_event: dict):
        return None

    class StubDetector:
        def check_log(self, _log_entry: dict) -> dict:
            return {
                "type": "ssh_brute_force",
                "severity": "high",
                "source_ip": "10.0.0.55",
                "description": "ssh brute force detected",
                "raw_log": "raw",
            }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("ws.agent.enqueue_write", direct_enqueue)
    monkeypatch.setattr("security.audit.enqueue_write", direct_enqueue)
    monkeypatch.setattr("ws.frontend.broadcast", noop_broadcast)
    monkeypatch.setattr("ws.agent._detector", StubDetector())

    init_deployment_role("standby", "standby-test-node", "/tmp/nullius-standby-test.lock")
    await _handle_log({
        "timestamp": now,
        "data": {
            "source": "auth",
            "line": "Failed password for root from 10.0.0.55 port 22 ssh2",
            "file": "/var/log/auth.log",
        },
    })
    await asyncio.sleep(0.05)
    monkeypatch.undo()

    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT action_taken FROM security_events WHERE source_ip = ? ORDER BY id DESC LIMIT 1",
            ("10.0.0.55",),
        )
        event_row = await cursor.fetchone()
        cursor = await conn.execute(
            "SELECT status, details FROM response_audit WHERE source_ip = ? AND stage = 'decision' ORDER BY id DESC LIMIT 1",
            ("10.0.0.55",),
        )
        audit_row = await cursor.fetchone()
    finally:
        await conn.close()

    assert event_row["action_taken"] == "review_required"
    assert audit_row["status"] == "review"
    assert "standby_passive_node" in str(audit_row["details"])
