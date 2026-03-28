# Тесты WebSocket-обработчика агента: auth, ping, отклонение без auth
import asyncio

import pytest
from starlette.testclient import TestClient
from tests.conftest import TEST_AGENT_SECRET
import db as db_module
from db import get_db, start_writer, stop_writer


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
