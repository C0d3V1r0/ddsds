# Тесты WebSocket-обработчика агента: auth, ping, отклонение без auth
import pytest
from starlette.testclient import TestClient
from tests.conftest import TEST_AGENT_SECRET


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
