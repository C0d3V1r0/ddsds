# Telegram-интеграция Nullius: подключение бота, polling команд и уведомления.
import asyncio
import ipaddress
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from api import health
from api.risk import calculate_risk_score
from api.security import _build_incidents
from db import get_db, enqueue_write
from integrations.policy import (
    normalize_notify_min_severity,
    normalize_quiet_time,
    should_notify_by_policy,
)
from security.audit import append_response_audit, make_trace_id
from security.mode import get_operation_mode

_logger = logging.getLogger("nullius.integrations.telegram")

_telegram_loop_task: asyncio.Task | None = None
_telegram_config = None


def init_telegram_runtime(config) -> None:
    global _telegram_config
    _telegram_config = config


async def get_telegram_settings() -> dict[str, object]:
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM telegram_settings WHERE id = 1")
        row = await cursor.fetchone()
        if not row:
            return _empty_telegram_settings()
        return _serialize_settings(dict(row))
    finally:
        await conn.close()


async def configure_telegram_bot(
    *,
    token: str,
    notify_auto_block: bool,
    notify_high_severity: bool,
    notify_min_severity: str,
    quiet_hours_start: str,
    quiet_hours_end: str,
) -> dict[str, object]:
    cleaned_token = token.strip()
    if not cleaned_token:
        await _reset_telegram_settings()
        return await get_telegram_settings()

    bot_info = await _telegram_api(cleaned_token, "getMe")
    if not bool(bot_info.get("ok")):
        raise RuntimeError("Telegram token is invalid")

    result = dict(bot_info.get("result") or {})
    now = int(time.time())
    min_severity = normalize_notify_min_severity(notify_min_severity)
    quiet_start = normalize_quiet_time(quiet_hours_start)
    quiet_end = normalize_quiet_time(quiet_hours_end)
    await _write_settings_row(
        (
            1,
            cleaned_token,
            str(result.get("username", "") or ""),
            str(result.get("first_name", "") or ""),
            "",
            "",
            0,
            1 if notify_auto_block else 0,
            1 if notify_high_severity else 0,
            min_severity,
            quiet_start,
            quiet_end,
            "",
            now,
        )
    )
    return await get_telegram_settings()


async def send_telegram_test_message() -> dict[str, object]:
    settings = await _load_settings_row()
    if not settings["configured"]:
        raise RuntimeError("Telegram bot is not configured")
    if not settings["chat_bound"]:
        raise RuntimeError("Telegram chat is not linked yet")

    await _send_message(
        settings["bot_token"],
        settings["chat_id"],
        "Nullius: тестовое сообщение. Бот подключён и готов отправлять уведомления.",
    )
    return {"status": "sent"}


def _should_notify_event(settings: dict[str, object], event: dict[str, object]) -> bool:
    return should_notify_by_policy(settings, event)


def _build_event_message(event: dict[str, object]) -> str:
    action_taken = str(event.get("action_taken", "") or "logged")
    action_label = "автоблокировка" if action_taken == "auto_block" else "событие высокого уровня"
    return (
        f"Nullius alert: {action_label}\n"
        f"Тип: {event.get('type', '')}\n"
        f"Источник: {event.get('source_ip', '') or 'host'}\n"
        f"Уровень: {event.get('severity', '')}\n"
        f"Действие: {action_taken}\n"
        f"Рекомендация: {event.get('recommended_action', '') or 'review_event'}\n"
        f"Trace: {event.get('trace_id', '') or 'n/a'}"
    )


async def notify_security_event(event: dict[str, object]) -> None:
    settings = await _load_settings_row()
    if not settings["configured"] or not settings["chat_bound"] or not _should_notify_event(settings, event):
        return

    try:
        await _send_message(settings["bot_token"], settings["chat_id"], _build_event_message(event))
    except Exception as exc:
        _logger.warning("Не удалось отправить Telegram-уведомление", exc_info=True)
        await _set_last_error(str(exc))


async def run_telegram_poll_cycle() -> None:
    settings = await _load_settings_row()
    if not settings["configured"]:
        return

    try:
        payload = await _telegram_api(
            settings["bot_token"],
            "getUpdates",
            {
                "offset": int(settings["last_update_id"]) + 1,
                "timeout": 0,
                "allowed_updates": json.dumps(["message"]),
            },
        )
    except Exception as exc:
        _logger.warning("Ошибка polling Telegram", exc_info=True)
        await _set_last_error(str(exc))
        return

    if not bool(payload.get("ok")):
        await _set_last_error("Telegram getUpdates failed")
        return

    updates = list(payload.get("result") or [])
    if not updates:
        return

    last_update_id = int(settings["last_update_id"])
    for update in updates:
        last_update_id = max(last_update_id, int(update.get("update_id", 0)))
        await _handle_update(update, settings)

    await enqueue_write(
        "UPDATE telegram_settings SET last_update_id = ?, last_error = '', updated_at = ? WHERE id = 1",
        (last_update_id, int(time.time())),
    )


async def _handle_update(update: dict[str, object], settings: dict[str, object]) -> None:
    message = dict(update.get("message") or {})
    text = str(message.get("text", "") or "").strip()
    if not text:
        return

    chat = dict(message.get("chat") or {})
    chat_id = str(chat.get("id", "") or "")
    chat_title = _chat_title(chat)

    if text.startswith("/start"):
        await _update_chat_binding(chat_id, chat_title)
        settings["chat_bound"] = True
        settings["chat_id"] = chat_id
        settings["chat_title"] = chat_title
        await _send_message(
            settings["bot_token"],
            chat_id,
            "Nullius: бот подключён.\nЭто оперативный канал уведомлений и быстрых команд.\nКоманды: /status, /risk, /incidents, /blocked, /mode, /block <ip> [reason], /unblock <ip>, /help",
        )
        return

    if not settings["chat_bound"]:
        return

    if text.startswith("/help"):
        await _send_message(
            settings["bot_token"],
            chat_id,
            "Nullius commands:\n/status — состояние платформы\n/risk — текущий риск\n/incidents — последние инциденты\n/blocked — последние блокировки\n/mode — текущий режим работы\n/block <ip> [reason] — экстренно заблокировать IP\n/unblock <ip> — снять блокировку",
        )
    elif text.startswith("/status"):
        await _send_message(settings["bot_token"], chat_id, await _build_status_message())
    elif text.startswith("/risk"):
        await _send_message(settings["bot_token"], chat_id, await _build_risk_message())
    elif text.startswith("/incidents"):
        await _send_message(settings["bot_token"], chat_id, await _build_incidents_message())
    elif text.startswith("/blocked"):
        await _send_message(settings["bot_token"], chat_id, await _build_blocked_message())
    elif text.startswith("/mode"):
        await _send_message(settings["bot_token"], chat_id, _build_mode_message())
    elif text.startswith("/block"):
        await _send_message(settings["bot_token"], chat_id, await _handle_block_command(text))
    elif text.startswith("/unblock"):
        await _send_message(settings["bot_token"], chat_id, await _handle_unblock_command(text))


async def _build_status_message() -> str:
    return (
        "Nullius status\n"
        f"API: {'ok' if health._db_ok else 'degraded'}\n"
        f"Agent: {'connected' if health._agent_connected else 'disconnected'}\n"
        f"DB: {'ok' if health._db_ok else 'error'}\n"
        f"Mode: {get_operation_mode()}"
    )


async def _build_risk_message() -> str:
    conn = await get_db()
    try:
        now = int(time.time())
        cursor = await conn.execute("SELECT timestamp FROM metrics ORDER BY timestamp DESC LIMIT 1")
        latest_metrics = await cursor.fetchone()
        latest_metrics_ts = int(latest_metrics["timestamp"]) if latest_metrics else None

        cursor = await conn.execute("SELECT name, status FROM services")
        services = [dict(row) for row in await cursor.fetchall()]

        cursor = await conn.execute(
            "SELECT type, severity, source_ip, action_taken FROM security_events WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 100",
            (now - 900,),
        )
        recent_events = [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()

    allowed_services = tuple(getattr(getattr(_telegram_config, "security", None), "allowed_services", []))
    risk = calculate_risk_score(
        api_ok=True,
        agent_connected=health._agent_connected,
        db_ok=health._db_ok,
        latest_metrics_ts=latest_metrics_ts,
        services=services,
        recent_events=recent_events,
        allowed_services=allowed_services,
        now=now,
    )
    return f"Nullius risk\nScore: {risk['score']}\nLevel: {risk['level']}"


async def _build_incidents_message() -> str:
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM security_events ORDER BY timestamp DESC LIMIT 50")
        rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()

    incidents = _build_incidents(rows)[:3]
    if not incidents:
        return "Nullius incidents\nNo incidents yet."

    lines = ["Nullius incidents"]
    for incident in incidents:
        lines.append(
            f"- {incident['type']} · {incident['severity']} · {incident['source_ip'] or 'host'} · {incident['event_count']} events"
        )
    return "\n".join(lines)


async def _build_blocked_message() -> str:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT ip, reason, expires_at FROM blocked_ips ORDER BY blocked_at DESC LIMIT 3"
        )
        rows = [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()

    if not rows:
        return "Nullius blocked IPs\nNo blocked IPs."

    lines = ["Nullius blocked IPs"]
    for row in rows:
        expires = str(row.get("expires_at", "") or "never")
        lines.append(f"- {row['ip']} · expires: {expires}")
    return "\n".join(lines)


def _build_mode_message() -> str:
    return f"Nullius mode\nCurrent mode: {get_operation_mode()}"


def _parse_ip(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        return None


async def _handle_block_command(text: str) -> str:
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        return "Nullius block\nUsage: /block <ip> [reason]"

    ip = _parse_ip(parts[1])
    if not ip:
        return "Nullius block\nInvalid IP address."

    reason = parts[2].strip() if len(parts) > 2 else "telegram_manual_block"
    now = int(time.time())
    trace_id = make_trace_id()
    await append_response_audit(
        trace_id=trace_id,
        stage="manual_action",
        status="blocked",
        source_ip=ip,
        action="manual_block",
        details={"reason": reason, "origin": "telegram_bot"},
        timestamp=now,
    )
    await enqueue_write(
        "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) VALUES (?, ?, ?, ?, 0)",
        (ip, reason[:500], now, None),
    )
    return f"Nullius block\nBlocked: {ip}\nReason: {reason}\nTrace: {trace_id}"


async def _handle_unblock_command(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "Nullius unblock\nUsage: /unblock <ip>"

    ip = _parse_ip(parts[1])
    if not ip:
        return "Nullius unblock\nInvalid IP address."

    trace_id = make_trace_id()
    await append_response_audit(
        trace_id=trace_id,
        stage="manual_action",
        status="unblocked",
        source_ip=ip,
        action="manual_unblock",
        details={"origin": "telegram_bot"},
        timestamp=int(time.time()),
    )
    await enqueue_write("DELETE FROM blocked_ips WHERE ip = ?", (ip,))
    return f"Nullius unblock\nUnblocked: {ip}\nTrace: {trace_id}"


def schedule_security_event_notification(event: dict[str, object]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(notify_security_event(event))


def start_telegram_loop() -> asyncio.Task:
    async def _loop():
        while True:
            try:
                await run_telegram_poll_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                _logger.warning("Telegram loop завершился ошибкой", exc_info=True)
            await asyncio.sleep(5)

    global _telegram_loop_task
    _telegram_loop_task = asyncio.create_task(_loop())
    return _telegram_loop_task


async def stop_telegram_loop() -> None:
    global _telegram_loop_task
    if _telegram_loop_task is None:
        return
    _telegram_loop_task.cancel()
    await asyncio.gather(_telegram_loop_task, return_exceptions=True)
    _telegram_loop_task = None


async def _load_settings_row() -> dict[str, object]:
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM telegram_settings WHERE id = 1")
        row = await cursor.fetchone()
        if not row:
            return _empty_telegram_settings()
        raw = dict(row)
        return {
            "configured": bool(str(raw.get("bot_token", "") or "").strip()),
            "bot_token": str(raw.get("bot_token", "") or ""),
            "bot_username": str(raw.get("bot_username", "") or ""),
            "bot_name": str(raw.get("bot_name", "") or ""),
            "chat_bound": bool(str(raw.get("chat_id", "") or "").strip()),
            "chat_id": str(raw.get("chat_id", "") or ""),
            "chat_title": str(raw.get("chat_title", "") or ""),
            "last_update_id": int(raw.get("last_update_id", 0) or 0),
            "notify_auto_block": bool(int(raw.get("notify_auto_block", 1) or 0)),
            "notify_high_severity": bool(int(raw.get("notify_high_severity", 0) or 0)),
            "notify_min_severity": normalize_notify_min_severity(str(raw.get("notify_min_severity", "high") or "high")),
            "quiet_hours_start": str(raw.get("quiet_hours_start", "") or ""),
            "quiet_hours_end": str(raw.get("quiet_hours_end", "") or ""),
            "last_error": str(raw.get("last_error", "") or ""),
            "updated_at": int(raw.get("updated_at", 0) or 0),
        }
    finally:
        await conn.close()


def _serialize_settings(raw: dict[str, object]) -> dict[str, object]:
    token = str(raw.get("bot_token", "") or "")
    chat_id = str(raw.get("chat_id", "") or "")
    return {
        "configured": bool(token),
        "bot_username": str(raw.get("bot_username", "") or ""),
        "bot_name": str(raw.get("bot_name", "") or ""),
        "chat_bound": bool(chat_id),
        "chat_title": str(raw.get("chat_title", "") or ""),
        "notify_auto_block": bool(int(raw.get("notify_auto_block", 1) or 0)),
        "notify_high_severity": bool(int(raw.get("notify_high_severity", 0) or 0)),
        "notify_min_severity": normalize_notify_min_severity(str(raw.get("notify_min_severity", "high") or "high")),
        "quiet_hours_start": str(raw.get("quiet_hours_start", "") or ""),
        "quiet_hours_end": str(raw.get("quiet_hours_end", "") or ""),
        "last_error": str(raw.get("last_error", "") or ""),
        "updated_at": int(raw.get("updated_at", 0) or 0),
    }


def _empty_telegram_settings() -> dict[str, object]:
    return {
        "configured": False,
        "bot_username": "",
        "bot_name": "",
        "chat_bound": False,
        "chat_title": "",
        "notify_auto_block": True,
        "notify_high_severity": False,
        "notify_min_severity": "high",
        "quiet_hours_start": "",
        "quiet_hours_end": "",
        "last_error": "",
        "updated_at": 0,
    }


async def _reset_telegram_settings() -> None:
    await _write_settings_row((1, "", "", "", "", "", 0, 1, 0, "high", "", "", "", int(time.time())))


async def _write_settings_row(values: tuple[object, ...]) -> None:
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT OR REPLACE INTO telegram_settings (
                id, bot_token, bot_username, bot_name, chat_id, chat_title, last_update_id,
                notify_auto_block, notify_high_severity, notify_min_severity, quiet_hours_start,
                quiet_hours_end, last_error, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        await conn.commit()
    finally:
        await conn.close()


async def _update_chat_binding(chat_id: str, chat_title: str) -> None:
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE telegram_settings SET chat_id = ?, chat_title = ?, last_error = '', updated_at = ? WHERE id = 1",
            (chat_id, chat_title, int(time.time())),
        )
        await conn.commit()
    finally:
        await conn.close()


async def _set_last_error(error: str) -> None:
    await enqueue_write(
        "UPDATE telegram_settings SET last_error = ?, updated_at = ? WHERE id = 1",
        (error[:500], int(time.time())),
    )


def _chat_title(chat: dict[str, object]) -> str:
    title = str(chat.get("title", "") or "").strip()
    if title:
        return title
    username = str(chat.get("username", "") or "").strip()
    if username:
        return f"@{username}"
    first_name = str(chat.get("first_name", "") or "").strip()
    last_name = str(chat.get("last_name", "") or "").strip()
    return " ".join(part for part in (first_name, last_name) if part).strip()


async def _send_message(token: str, chat_id: str, text: str) -> dict[str, object]:
    return await _telegram_api(token, "sendMessage", {"chat_id": chat_id, "text": text})


async def _telegram_api(token: str, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
    return await asyncio.to_thread(_telegram_api_sync, token, method, params or {})


def _telegram_api_sync(token: str, method: str, params: dict[str, object]) -> dict[str, object]:
    encoded = urllib.parse.urlencode({key: str(value) for key, value in params.items()}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=encoded if params else None,
        method="POST" if params else "GET",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        raise RuntimeError(body or f"Telegram HTTP error {exc.code}") from exc
