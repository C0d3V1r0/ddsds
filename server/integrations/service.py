# Общий сервис интеграций: единая точка запуска и fan-out уведомлений.
import time
from typing import Awaitable

from integrations.slack import schedule_security_event_notification as schedule_slack_notification
from integrations.telegram import (
    init_telegram_runtime,
    schedule_security_event_notification as schedule_telegram_notification,
    start_telegram_loop,
    stop_telegram_loop,
)

NOTIFICATION_DEDUP_WINDOW = 300
_recent_notifications: dict[tuple[str, str, str], int] = {}


def init_integrations_runtime(config) -> None:
    """Инициализирует stateful-части внешних интеграций."""
    init_telegram_runtime(config)


def start_integrations_loops() -> list[Awaitable]:
    """Запускает фоновые циклы интеграций, которым нужен polling."""
    return [start_telegram_loop()]


async def stop_integrations_loops() -> None:
    """Останавливает фоновые интеграционные циклы."""
    await stop_telegram_loop()


def _notification_key(event: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(event.get("type", "") or ""),
        str(event.get("source_ip", "") or ""),
        str(event.get("action_taken", "") or ""),
    )


def should_emit_notification(event: dict[str, object], now: int | None = None) -> bool:
    """Подавляет близкие дубликаты уведомлений, чтобы каналы не превращались в шум."""
    effective_now = now or int(time.time())
    key = _notification_key(event)
    last_sent_at = _recent_notifications.get(key, 0)
    if last_sent_at and effective_now - last_sent_at < NOTIFICATION_DEDUP_WINDOW:
        return False

    _recent_notifications[key] = effective_now
    stale_before = effective_now - NOTIFICATION_DEDUP_WINDOW
    for stale_key, sent_at in list(_recent_notifications.items()):
        if sent_at < stale_before:
            _recent_notifications.pop(stale_key, None)
    return True


def schedule_security_event_notifications(event: dict[str, object]) -> None:
    """Рассылает security event во внешние каналы по их локальным правилам."""
    if not should_emit_notification(event):
        return
    schedule_telegram_notification(event)
    schedule_slack_notification(event)
