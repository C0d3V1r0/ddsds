# - WebSocket-обработчик фронтенда: подключение клиентов и broadcast событий
import asyncio
import hmac
import logging
from fastapi import WebSocket, WebSocketDisconnect

_logger = logging.getLogger("nullius.ws.frontend")
_clients: set[WebSocket] = set()

# - Максимальное количество одновременных WS-подключений фронтенда
MAX_WS_CLIENTS = 100


async def frontend_ws_handler(ws: WebSocket, api_token: str) -> None:
    # - Ограничение количества подключений для защиты от исчерпания ресурсов
    if len(_clients) >= MAX_WS_CLIENTS:
        await ws.close(code=1008)
        return
    await ws.accept()
    # - Проверка токена в первом сообщении
    try:
        first_msg = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
        if not hmac.compare_digest(first_msg.get("token", ""), api_token):
            await ws.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await ws.close(code=4001, reason="Unauthorized")
        return
    _clients.add(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


async def broadcast(event: dict) -> None:
    # - Рассылаем событие всем подключённым фронтенд-клиентам, итерируемся по копии
    disconnected: set[WebSocket] = set()
    for ws in list(_clients):
        try:
            await ws.send_json(event)
        except WebSocketDisconnect:
            disconnected.add(ws)
        except Exception:
            _logger.warning(f"# - Ошибка broadcast клиенту: {ws}", exc_info=True)
            disconnected.add(ws)
    _clients -= disconnected
