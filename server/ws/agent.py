# WebSocket-обработчик агента: аутентификация, приём метрик, логов, сервисов, процессов
import hmac
import json
import logging
import time
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from deployment import active_response_enabled
from db import enqueue_write, get_db
from api.logs import append_log
from api.processes import update_processes
from api import health
from integrations.service import schedule_security_event_notifications
from security.audit import append_response_audit, extract_audit_meta, make_trace_id, sanitize_command_params
from security.mode import get_operation_mode

_logger = logging.getLogger("nullius.ws.agent")

# Длительность блокировки IP по умолчанию (24 часа)
DEFAULT_BLOCK_DURATION = 86400
MAX_LOG_LINE_CHARS = 4096
MAX_LOG_SOURCE_CHARS = 64
MAX_LOG_FILE_CHARS = 512
ACTIVE_RESPONSE_COMMANDS = {"block_ip", "unblock_ip", "restart_service", "kill_process", "force_kill_process"}

_agent_ws: WebSocket | None = None
_detector = None
_config = None
_ml_config = None
_pending_command_results: dict[str, asyncio.Future] = {}


def get_agent_ws() -> WebSocket | None:
    return _agent_ws


def init_security(detector, config=None, ml_config=None):
    global _detector, _config, _ml_config
    _detector = detector
    _config = config
    _ml_config = ml_config


async def _load_response_context(event: dict, timestamp: int) -> dict[str, object]:
    """Собирает минимальный контекст для response policy: повторяемость и cooldown."""
    source_ip = str(event.get("source_ip", "")).strip()
    if not source_ip or _config is None:
        return {
            "recent_events_count": 1,
            "cooldown_active": False,
            "currently_blocked": False,
            "recent_duplicate": None,
        }

    recent_events_count = 1
    cooldown_active = False
    currently_blocked = False
    recent_duplicate = None
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM security_events WHERE type = ? AND source_ip = ? AND timestamp >= ?",
            (
                str(event.get("type", "")),
                source_ip,
                timestamp - int(_config.medium_escalation_window),
            ),
        )
        row = await cursor.fetchone()
        recent_events_count = int((row[0] if row else 0) or 0) + 1

        cursor = await conn.execute(
            "SELECT blocked_at, expires_at FROM blocked_ips WHERE ip = ?",
            (source_ip,),
        )
        blocked_row = await cursor.fetchone()
        if blocked_row:
            currently_blocked = True
            blocked_at = int(blocked_row["blocked_at"] or 0)
            expires_at = blocked_row["expires_at"]
            cooldown_active = (
                (expires_at is None and blocked_at >= timestamp - int(_config.response_cooldown))
                or (expires_at is not None and int(expires_at) > timestamp)
            )

        dedup_window = int(getattr(_config, "event_dedup_window", 300) or 300)
        cursor = await conn.execute(
            """
            SELECT id, action_taken, timestamp, description
            FROM security_events
            WHERE type = ? AND source_ip = ? AND timestamp >= ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """,
            (
                str(event.get("type", "")),
                source_ip,
                timestamp - dedup_window,
            ),
        )
        duplicate_row = await cursor.fetchone()
        if duplicate_row:
            recent_duplicate = {
                "id": int(duplicate_row["id"]),
                "action_taken": str(duplicate_row["action_taken"] or ""),
                "timestamp": int(duplicate_row["timestamp"] or 0),
                "description": str(duplicate_row["description"] or ""),
            }
    finally:
        await conn.close()

    return {
        "recent_events_count": recent_events_count,
        "cooldown_active": cooldown_active,
        "currently_blocked": currently_blocked,
        "recent_duplicate": recent_duplicate,
    }


def _should_suppress_followup_event(event: dict, response_context: dict[str, object]) -> bool:
    """Подавляет шумные follow-up события от уже заблокированного IP.

    Это нужно не для сокрытия атаки, а чтобы не плодить одинаковые алерты,
    когда трафик уже дропается и оператору важнее видеть сам факт блокировки.
    """
    if not bool(response_context.get("currently_blocked")):
        return False
    return str(event.get("type", "")) == "port_scan"


def _should_suppress_duplicate_event(
    event: dict,
    action_taken: str,
    response_context: dict[str, object],
) -> bool:
    """Подавляет только близкие дубликаты с тем же действием, не ломая эскалацию."""
    duplicate = response_context.get("recent_duplicate")
    if not isinstance(duplicate, dict):
        return False
    if str(duplicate.get("action_taken", "")) != action_taken:
        return False
    if str(duplicate.get("description", "")) != str(event.get("description", "")):
        return False
    return True


async def agent_ws_handler(ws: WebSocket, secret: str):
    global _agent_ws
    await ws.accept()
    # Первое сообщение должно быть auth с корректным секретом
    try:
        msg = await ws.receive_json()
        # Timing-safe сравнение для защиты от атак по времени отклика
        if not isinstance(msg, dict):
            await ws.send_json({"type": "auth_error", "error": "invalid secret"})
            await ws.close(code=4001)
            return
        if msg.get("type") != "auth" or not hmac.compare_digest(str(msg.get("secret", "")), secret):
            await ws.send_json({"type": "auth_error", "error": "invalid secret"})
            await ws.close(code=4001)
            return
        await ws.send_json({"type": "auth_ok"})
    except WebSocketDisconnect:
        return
    except (TypeError, ValueError) as exc:
        _logger.warning(f"Ошибка при аутентификации агента: {exc}")
        await ws.close(code=4001)
        return

    # Закрываем предыдущее подключение агента, если оно существует
    if _agent_ws is not None:
        _logger.warning("Новое подключение агента вытесняет предыдущее")
        try:
            await _agent_ws.close(code=4000)
        except RuntimeError:
            _logger.debug("Предыдущее WS-подключение агента уже недоступно во время вытеснения", exc_info=True)
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
                cmd_id = str(msg.get("id", ""))
                future = _pending_command_results.pop(cmd_id, None)
                if future and not future.done():
                    future.set_result(msg)
                audit_meta = extract_audit_meta(msg.get("params", {}))
                await append_response_audit(
                    trace_id=audit_meta.get("trace_id", ""),
                    stage="command_result",
                    status=str(msg.get("status", "unknown") or "unknown"),
                    event_type=audit_meta.get("event_type", ""),
                    source_ip=audit_meta.get("source_ip", ""),
                    action=audit_meta.get("action", ""),
                    command=str(msg.get("command", "") or ""),
                    details={
                        "origin": audit_meta.get("origin", ""),
                        "params": sanitize_command_params(msg.get("params", {})),
                        "error": str(msg.get("error", "") or ""),
                    },
                )
                # Сохраняем результат команды в таблицу agent_commands
                await enqueue_write(
                    "INSERT INTO agent_commands (timestamp, command, params, result, error, trace_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (int(time.time()), msg.get("command", ""),
                     json.dumps(msg.get("params", {})),
                     msg.get("status", ""), msg.get("error", ""), audit_meta.get("trace_id", ""))
                )
            elif msg_type == "disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        _agent_ws = None
        health.set_agent_status(False)


def _validate_timestamp(ts: object) -> int:
    """Проверяет что timestamp — целое число в разумном диапазоне (последние 24ч, не в будущем)"""
    now = int(time.time())
    if not isinstance(ts, int):
        return now
    # Допускаем 5 минут в будущем для компенсации рассинхрона часов
    if ts > now + 300 or ts < now - 86400:
        return now
    return ts


async def _handle_metrics(msg: dict):
    data = msg.get("data", {})
    if not isinstance(data, dict):
        _logger.warning("Невалидный формат data в metrics: ожидается dict")
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

    # ML: проверяем метрики на аномалии через Isolation Forest
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
                trace_id = make_trace_id()
                event = {
                    "type": "anomaly",
                    "severity": "medium",
                    "source_ip": "",
                    "description": f"ML anomaly detected (score: {result['score']:.3f})",
                    "raw_log": json.dumps(flat),
                    "action_taken": "review_required",
                    "trace_id": trace_id,
                }
                await append_response_audit(
                    trace_id=trace_id,
                    stage="detected",
                    status="event_created",
                    event_type=event["type"],
                    source_ip="",
                    action=event["action_taken"],
                    details={
                        "signal_source": "ml_metrics_detector",
                        "score": round(float(result["score"]), 4),
                    },
                    timestamp=ts,
                )
                await enqueue_write(
                    "INSERT INTO security_events (timestamp, type, severity, source_ip, description, raw_log, action_taken, trace_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (ts, event["type"], event["severity"], "", event["description"], event["raw_log"], event["action_taken"], trace_id)
                )
                from ws.frontend import broadcast
                await broadcast({"type": "security_event", "data": event})
    except Exception as exc:
        _logger.debug(f"ML anomaly check пропущен: {exc}")


async def _handle_log(msg: dict):
    data = msg.get("data", {})
    if not isinstance(data, dict):
        _logger.warning("Невалидный формат data в log_event: ожидается dict")
        return
    log_entry = {
        "timestamp": _validate_timestamp(msg.get("timestamp", int(time.time()))),
        "source": str(data.get("source", ""))[:MAX_LOG_SOURCE_CHARS],
        "line": str(data.get("line", ""))[:MAX_LOG_LINE_CHARS],
        "file": str(data.get("file", ""))[:MAX_LOG_FILE_CHARS],
    }
    ts = log_entry["timestamp"]
    append_log(log_entry)
    from ws.frontend import broadcast
    await broadcast({"type": "log", "data": log_entry})

    # ML: классификатор как second opinion для логов
    ml_event = None
    try:
        from ml.trainer import get_classifier
        from ml.features import extract_log_features
        classifier = get_classifier()
        if classifier.is_ready():
            text = extract_log_features(data.get("line", ""))
            ml_result = classifier.predict(text)
            ml_event = ml_result
    except Exception as exc:
        _logger.debug(f"ML classify пропущен: {exc}")

    if _detector is None:
        return
    from security.integration import merge_log_detection
    event = merge_log_detection(
        _detector.check_log(data),
        ml_event,
        raw_log=str(data.get("line", "")),
        # Порог ML живёт в ML-конфиге, но оставляем мягкий фоллбэк для старых тестов.
        ml_min_confidence=float(getattr(_ml_config, "log_classifier_min_confidence", 0.6)) if _ml_config else 0.6,
    )

    if event is None:
        return
    from security.responder import decide_response
    trace_id = make_trace_id()

    response_context = await _load_response_context(event, int(ts))
    action = decide_response(
        event,
        operation_mode=get_operation_mode(),
        auto_block=bool(_config.auto_block) if _config else True,
        recent_events_count=int(response_context["recent_events_count"]),
        medium_escalation_threshold=int(_config.medium_escalation_threshold) if _config else 3,
        cooldown_active=bool(response_context["cooldown_active"]),
    )
    if not active_response_enabled() and action["action"] == "block":
        # Standby-узел может анализировать сигналы, но не должен выполнять containment/block.
        action = {
            **action,
            "action": "review",
            "stage": "observe",
            "reason": "standby_passive_node",
            "operator_priority": "high",
        }
    action_taken = "logged"
    if action["action"] == "review":
        action_taken = "review_required"
    elif action["action"] == "block":
        action_taken = "auto_block"

    event["action_taken"] = action_taken
    event["trace_id"] = trace_id
    await append_response_audit(
        trace_id=trace_id,
        stage="detected",
        status="event_created",
        event_type=str(event["type"]),
        source_ip=str(event.get("source_ip", "")),
        action=action_taken,
        details={
            "severity": str(event["severity"]),
            "description": str(event["description"]),
            "recent_events_count": int(response_context["recent_events_count"]),
            "cooldown_active": bool(response_context["cooldown_active"]),
        },
        timestamp=ts,
    )
    await append_response_audit(
        trace_id=trace_id,
        stage="decision",
        status=action["action"],
        event_type=str(event["type"]),
        source_ip=str(event.get("source_ip", "")),
        action=action_taken,
        details={
            "policy_action": action["action"],
            "policy_stage": action.get("stage", ""),
            "reason": action.get("reason", ""),
            "operator_priority": action.get("operator_priority", ""),
            "operation_mode": get_operation_mode(),
            "recent_events_count": int(response_context["recent_events_count"]),
            "cooldown_active": bool(response_context["cooldown_active"]),
            "currently_blocked": bool(response_context["currently_blocked"]),
        },
        timestamp=ts,
    )
    if _should_suppress_followup_event(event, response_context):
        await append_response_audit(
            trace_id=trace_id,
            stage="decision",
            status="suppressed",
            event_type=str(event["type"]),
            source_ip=str(event.get("source_ip", "")),
            action=action_taken,
            details={
                "reason": "already_blocked_followup",
                "recent_events_count": int(response_context["recent_events_count"]),
            },
            timestamp=ts,
        )
        return
    if _should_suppress_duplicate_event(event, action_taken, response_context):
        await append_response_audit(
            trace_id=trace_id,
            stage="decision",
            status="suppressed_duplicate",
            event_type=str(event["type"]),
            source_ip=str(event.get("source_ip", "")),
            action=action_taken,
            details={
                "reason": "recent_duplicate_event",
                "existing_event_id": int(response_context["recent_duplicate"]["id"]),
            },
            timestamp=ts,
        )
        return
    await enqueue_write(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, raw_log, action_taken, trace_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, event["type"], event["severity"], event.get("source_ip", ""),
         event["description"], event.get("raw_log", ""), action_taken, trace_id)
    )
    if action["action"] == "block":
        # Длительность блокировки берём из конфига, 86400 — фоллбэк по умолчанию
        block_duration = _config.ssh_brute_force.block_duration if _config else DEFAULT_BLOCK_DURATION
        await send_command(
            "block_ip",
            {
                "ip": action["ip"],
                "duration": block_duration,
                "_meta": {
                    "trace_id": trace_id,
                    "event_type": str(event["type"]),
                    "source_ip": str(action["ip"]),
                    "action": action_taken,
                    "origin": "auto_response",
                },
            },
        )
        await enqueue_write(
            "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
            "VALUES (?, ?, ?, ?, 1)",
            (action["ip"], event["description"], ts, ts + block_duration)
        )
        schedule_security_event_notifications(event)
    elif str(event.get("severity", "")) in {"high", "critical"}:
        schedule_security_event_notifications(event)
    await broadcast({"type": "security_event", "data": event})


async def _handle_services(msg: dict):
    services = msg.get("data", [])
    if not isinstance(services, list):
        _logger.warning("Невалидный формат data в services: ожидается list")
        return
    now = int(time.time())
    for svc in services:
        await enqueue_write(
            "INSERT OR REPLACE INTO services (name, status, pid, uptime, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (svc.get("name"), svc.get("status"), svc.get("pid"), svc.get("uptime"), now)
        )


async def send_command(command: str, params: dict, await_result: bool = False, timeout: float = 6.0) -> dict | None:
    if not active_response_enabled() and command in ACTIVE_RESPONSE_COMMANDS:
        raise RuntimeError("Current node is in standby mode and cannot execute active response commands")
    ws = get_agent_ws()
    if ws:
        cmd_id = f"cmd_{int(time.time() * 1000)}"
        future: asyncio.Future | None = None
        if await_result:
            future = asyncio.get_running_loop().create_future()
            _pending_command_results[cmd_id] = future
        await ws.send_json({"id": cmd_id, "command": command, "params": params})
        audit_meta = extract_audit_meta(params)
        await append_response_audit(
            trace_id=audit_meta.get("trace_id", ""),
            stage="command_dispatched",
            status="queued",
            event_type=audit_meta.get("event_type", ""),
            source_ip=audit_meta.get("source_ip", ""),
            action=audit_meta.get("action", ""),
            command=command,
            details={
                "origin": audit_meta.get("origin", ""),
                "params": sanitize_command_params(params),
            },
        )
        if not future:
            return None
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            _pending_command_results.pop(cmd_id, None)
            raise
    return None
