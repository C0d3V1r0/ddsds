# Slack-интеграция Nullius: отправка уведомлений через Incoming Webhook.
import asyncio
import json
import logging
import time
import urllib.error
import urllib.request

from db import get_db

_logger = logging.getLogger("nullius.integrations.slack")


async def get_slack_settings() -> dict[str, object]:
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM slack_settings WHERE id = 1")
        row = await cursor.fetchone()
        if not row:
            return _empty_slack_settings()
        return _serialize_settings(dict(row))
    finally:
        await conn.close()


async def configure_slack_webhook(
    *,
    webhook_url: str,
    notify_auto_block: bool,
    notify_high_severity: bool,
) -> dict[str, object]:
    cleaned_webhook = webhook_url.strip()
    if not cleaned_webhook:
        await _write_settings_row((1, "", 1, 0, "", int(time.time())))
        return await get_slack_settings()

    if not cleaned_webhook.startswith("https://hooks.slack.com/"):
        raise RuntimeError("Slack webhook URL is invalid")

    await _write_settings_row((1, cleaned_webhook, 1 if notify_auto_block else 0, 1 if notify_high_severity else 0, "", int(time.time())))
    return await get_slack_settings()


async def send_slack_test_message() -> dict[str, object]:
    settings = await _load_settings_row()
    if not settings["configured"]:
        raise RuntimeError("Slack webhook is not configured")

    await _send_payload(
        settings["webhook_url"],
        {
            "text": "Nullius: тестовое сообщение. Slack webhook подключён и готов отправлять уведомления.",
        },
    )
    return {"status": "sent"}


def _should_notify_event(settings: dict[str, object], event: dict[str, object]) -> bool:
    action_taken = str(event.get("action_taken", "") or "")
    severity = str(event.get("severity", "") or "")
    if action_taken == "auto_block":
        return bool(settings["notify_auto_block"])
    return bool(settings["notify_high_severity"]) and severity in {"high", "critical"}


def _build_event_payload(event: dict[str, object]) -> dict[str, object]:
    action_taken = str(event.get("action_taken", "") or "logged")
    action_label = "автоблокировка" if action_taken == "auto_block" else "событие высокого уровня"
    severity = str(event.get("severity", "") or "")
    source_ip = str(event.get("source_ip", "") or "host")
    recommended_action = str(event.get("recommended_action", "") or "review_event")
    trace_id = str(event.get("trace_id", "") or "n/a")
    return {
        "text": f"Nullius: {action_label}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Nullius: {action_label}*\n"
                        f"*Тип:* {event.get('type', '')}\n"
                        f"*Источник:* {source_ip}\n"
                        f"*Уровень:* {severity}\n"
                        f"*Действие:* {action_taken}"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Рекомендация:* {recommended_action}"},
                    {"type": "mrkdwn", "text": f"*Trace:* {trace_id}"},
                ],
            },
        ],
    }


async def notify_security_event(event: dict[str, object]) -> None:
    settings = await _load_settings_row()
    if not settings["configured"] or not _should_notify_event(settings, event):
        return

    try:
        await _send_payload(settings["webhook_url"], _build_event_payload(event))
    except Exception as exc:
        _logger.warning("Не удалось отправить Slack-уведомление", exc_info=True)
        await _set_last_error(str(exc))


def schedule_security_event_notification(event: dict[str, object]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(notify_security_event(event))


async def _load_settings_row() -> dict[str, object]:
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM slack_settings WHERE id = 1")
        row = await cursor.fetchone()
        if not row:
            return _empty_slack_settings()
        raw = dict(row)
        return {
            "configured": bool(str(raw.get("webhook_url", "") or "").strip()),
            "webhook_url": str(raw.get("webhook_url", "") or ""),
            "notify_auto_block": bool(int(raw.get("notify_auto_block", 1) or 0)),
            "notify_high_severity": bool(int(raw.get("notify_high_severity", 0) or 0)),
            "last_error": str(raw.get("last_error", "") or ""),
            "updated_at": int(raw.get("updated_at", 0) or 0),
        }
    finally:
        await conn.close()


def _serialize_settings(raw: dict[str, object]) -> dict[str, object]:
    return {
        "configured": bool(str(raw.get("webhook_url", "") or "").strip()),
        "notify_auto_block": bool(int(raw.get("notify_auto_block", 1) or 0)),
        "notify_high_severity": bool(int(raw.get("notify_high_severity", 0) or 0)),
        "last_error": str(raw.get("last_error", "") or ""),
        "updated_at": int(raw.get("updated_at", 0) or 0),
    }


def _empty_slack_settings() -> dict[str, object]:
    return {
        "configured": False,
        "notify_auto_block": True,
        "notify_high_severity": False,
        "last_error": "",
        "updated_at": 0,
    }


async def _write_settings_row(values: tuple[object, ...]) -> None:
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT OR REPLACE INTO slack_settings (
                id, webhook_url, notify_auto_block, notify_high_severity, last_error, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        await conn.commit()
    finally:
        await conn.close()


async def _set_last_error(error: str) -> None:
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE slack_settings SET last_error = ?, updated_at = ? WHERE id = 1",
            (error[:500], int(time.time())),
        )
        await conn.commit()
    finally:
        await conn.close()


async def _send_payload(webhook_url: str, payload: dict[str, object]) -> None:
    await asyncio.to_thread(_send_payload_sync, webhook_url, payload)


def _send_payload_sync(webhook_url: str, payload: dict[str, object]) -> None:
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode().strip()
            if body not in {"ok", ""}:
                raise RuntimeError(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        raise RuntimeError(body or f"Slack HTTP error {exc.code}") from exc
