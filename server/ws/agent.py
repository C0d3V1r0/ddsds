# - WebSocket-обработчик агента: аутентификация, приём метрик, логов, сервисов, процессов
import hmac
import json
import logging
import time
from fastapi import WebSocket, WebSocketDisconnect
from db import enqueue_write
from api.logs import append_log
from api.processes import update_processes
from api import health

_logger = logging.getLogger("nullius.ws.agent")

# - Длительность блокировки IP по умолчанию (24 часа)
DEFAULT_BLOCK_DURATION = 86400

_agent_ws: WebSocket | None = None
_detector = None
_responder = None
_config = None


def get_agent_ws() -> WebSocket | None:
    return _agent_ws


def init_security(detector, responder, config=None):
    global _detector, _responder, _config
    _detector = detector
    _responder = responder
    _config = config


async def agent_ws_handler(ws: WebSocket, secret: str):
    global _agent_ws
    await ws.accept()
    # - Первое сообщение должно быть auth с корректным секретом
    try:
        msg = await ws.receive_json()
        # - Timing-safe сравнение для защиты от атак по времени отклика
        if msg.get("type") != "auth" or not hmac.compare_digest(msg.get("secret", ""), secret):
            await ws.send_json({"type": "auth_error", "error": "invalid secret"})
            await ws.close(code=4001)
            return
        await ws.send_json({"type": "auth_ok"})
    except WebSocketDisconnect:
        return
    except Exception as e:
        _logger.warning(f"# - Ошибка при аутентификации агента: {e}")
        await ws.close(code=4001)
        return

    # - Закрываем предыдущее подключение агента, если оно существует
    if _agent_ws is not None:
        _logger.warning("# - Новое подключение агента вытесняет предыдущее")
        try:
            await _agent_ws.close(code=4000)
        except Exception:
            pass
    _agent_ws = ws
    health.set_agent_status(True)
    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "metrics":
                await _handle_metrics(msg)
            elif msg_type == "log_event":
                await _handle_log(msg)
            elif msg_type == "services":
                await _handle_services(msg)
            elif msg_type == "processes":
                update_processes(msg.get("data", []))
            elif msg_type == "command_result":
                # - Сохраняем результат команды в таблицу agent_commands
                await enqueue_write(
                    "INSERT INTO agent_commands (timestamp, command, params, result, error) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (int(time.time()), msg.get("command", ""),
                     json.dumps(msg.get("params", {})),
                     msg.get("status", ""), msg.get("error", ""))
                )
            elif msg_type == "disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        _agent_ws = None
        health.set_agent_status(False)


def _validate_timestamp(ts: object) -> int:
    """- Проверяет что timestamp — целое число в разумном диапазоне (последние 24ч, не в будущем)"""
    now = int(time.time())
    if not isinstance(ts, int):
        return now
    # - Допускаем 5 минут в будущем для компенсации рассинхрона часов
    if ts > now + 300 or ts < now - 86400:
        return now
    return ts


async def _handle_metrics(msg: dict):
    data = msg.get("data", {})
    if not isinstance(data, dict):
        _logger.warning("# - Невалидный формат data в metrics: ожидается dict")
        return
    ts = _validate_timestamp(msg.get("timestamp", int(time.time())))
    cpu = data.get("cpu", {})
    ram = data.get("ram", {})
    net = data.get("network", {})
    await enqueue_write(
        "INSERT INTO metrics (timestamp, cpu_total, cpu_cores, ram_used, ram_total, "
        "network_rx, network_tx, load_avg, disk) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, cpu.get("total"), json.dumps(cpu.get("cores", [])),
         ram.get("used"), ram.get("total"),
         net.get("rx_bytes_delta"), net.get("tx_bytes_delta"),
         json.dumps(data.get("load_avg", [])), json.dumps(data.get("disk", [])))
    )

    # - ML: проверяем метрики на аномалии через Isolation Forest
    try:
        from ml.trainer import get_anomaly_detector
        from ml.features import extract_metrics_features
        detector = get_anomaly_detector()
        if detector.is_ready():
            flat = {
                "cpu_total": cpu.get("total", 0),
                "ram_used": ram.get("used", 0),
                "ram_total": ram.get("total", 1),
                "network_rx": net.get("rx_bytes_delta", 0),
                "network_tx": net.get("tx_bytes_delta", 0),
                "load_avg": json.dumps(data.get("load_avg", [])),
            }
            features = extract_metrics_features(flat)
            result = detector.predict(features)
            if result["is_anomaly"]:
                event = {
                    "type": "anomaly",
                    "severity": "medium",
                    "source_ip": "",
                    "description": f"ML anomaly detected (score: {result['score']:.3f})",
                    "raw_log": json.dumps(flat),
                }
                await enqueue_write(
                    "INSERT INTO security_events (timestamp, type, severity, source_ip, description, raw_log, action_taken) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ts, event["type"], event["severity"], "", event["description"], event["raw_log"], "ml_detection")
                )
                from ws.frontend import broadcast
                await broadcast({"type": "security_event", "data": event})
    except Exception as exc:
        _logger.debug(f"# - ML anomaly check пропущен: {exc}")


async def _handle_log(msg: dict):
    data = msg.get("data", {})
    if not isinstance(data, dict):
        _logger.warning("# - Невалидный формат data в log_event: ожидается dict")
        return
    log_entry = {
        "timestamp": _validate_timestamp(msg.get("timestamp", int(time.time()))),
        "source": data.get("source", ""),
        "line": data.get("line", ""),
        "file": data.get("file", ""),
    }
    append_log(log_entry)

    # - ML: классификатор как second opinion для логов
    ml_event = None
    try:
        from ml.trainer import get_classifier
        from ml.features import extract_log_features
        classifier = get_classifier()
        if classifier.is_ready():
            text = extract_log_features(data.get("line", ""))
            ml_result = classifier.predict(text)
            if ml_result["label"] not in ("normal", "unknown"):
                ml_event = ml_result
    except Exception as exc:
        _logger.debug(f"# - ML classify пропущен: {exc}")

    if _detector is None:
        return
    event = _detector.check_log(data)

    # - Если rule-based не сработал, но ML обнаружил атаку — создаём событие с low severity
    if event is None and ml_event is not None:
        ts = msg.get("timestamp", int(time.time()))
        event = {
            "type": ml_event["label"],
            "severity": "low",
            "source_ip": "",
            "description": f"ML-detected: {ml_event['label']}",
            "raw_log": data.get("line", ""),
        }
        await enqueue_write(
            "INSERT INTO security_events (timestamp, type, severity, source_ip, description, raw_log, action_taken) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, event["type"], event["severity"], "", event["description"], event["raw_log"], "ml_detection")
        )
        from ws.frontend import broadcast
        await broadcast({"type": "security_event", "data": event})
        return

    if event is None:
        return
    ts = msg.get("timestamp", int(time.time()))
    await enqueue_write(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, raw_log, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, event["type"], event["severity"], event.get("source_ip", ""),
         event["description"], event.get("raw_log", ""), "")
    )
    action = _responder.decide(event)
    if action["action"] == "block":
        # - Длительность блокировки берём из конфига, 86400 — фоллбэк по умолчанию
        block_duration = _config.ssh_brute_force.block_duration if _config else DEFAULT_BLOCK_DURATION
        await send_command("block_ip", {"ip": action["ip"], "duration": block_duration})
        await enqueue_write(
            "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
            "VALUES (?, ?, ?, ?, 1)",
            (action["ip"], event["description"], ts, ts + block_duration)
        )
    from ws.frontend import broadcast
    await broadcast({"type": "security_event", "data": event})


async def _handle_services(msg: dict):
    services = msg.get("data", [])
    if not isinstance(services, list):
        _logger.warning("# - Невалидный формат data в services: ожидается list")
        return
    now = int(time.time())
    for svc in services:
        await enqueue_write(
            "INSERT OR REPLACE INTO services (name, status, pid, uptime, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (svc.get("name"), svc.get("status"), svc.get("pid"), svc.get("uptime"), now)
        )


async def send_command(command: str, params: dict) -> None:
    ws = get_agent_ws()
    if ws:
        cmd_id = f"cmd_{int(time.time() * 1000)}"
        await ws.send_json({"id": cmd_id, "command": command, "params": params})
