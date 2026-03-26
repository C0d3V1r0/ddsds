# - Тесты WebSocket-обработчика фронтенда: подключение, auth и ping/pong
import pytest
from starlette.testclient import TestClient
from tests.conftest import TEST_AGENT_SECRET


@pytest.mark.asyncio
async def test_frontend_ws_connects(test_app):
    # - По умолчанию фронтенд-клиент подключается без отдельного WS-токена
    client = TestClient(test_app)
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"


@pytest.mark.asyncio
async def test_frontend_ws_connects_with_token_when_enabled(secure_test_app):
    # - При включённой WS-auth клиент должен передать корректный токен
    client = TestClient(secure_test_app)
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"token": TEST_AGENT_SECRET})
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"


@pytest.mark.asyncio
async def test_frontend_ws_rejects_invalid_token_when_enabled(secure_test_app):
    # - Фронтенд с невалидным токеном получает закрытие соединения
    client = TestClient(secure_test_app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"token": "wrong-token"})
            # - Сервер должен закрыть соединение после невалидного токена
            ws.receive_json()
