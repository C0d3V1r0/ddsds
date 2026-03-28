# Функции трассы реакции: trace_id и запись этапов response pipeline.
import json
import time
import uuid
from typing import Any

from db import enqueue_write


def make_trace_id() -> str:
    """Создаёт короткий, но достаточно уникальный идентификатор цепочки реакции."""
    return uuid.uuid4().hex[:16]


def extract_audit_meta(params: dict[str, Any] | None) -> dict[str, str]:
    """Достаёт служебные поля trail из params, не смешивая их с полезной нагрузкой команды."""
    if not isinstance(params, dict):
        return {}
    raw_meta = params.get("_meta")
    if not isinstance(raw_meta, dict):
        return {}
    return {
        "trace_id": str(raw_meta.get("trace_id", "")).strip(),
        "event_type": str(raw_meta.get("event_type", "")).strip(),
        "source_ip": str(raw_meta.get("source_ip", "")).strip(),
        "action": str(raw_meta.get("action", "")).strip(),
        "origin": str(raw_meta.get("origin", "")).strip(),
    }


def sanitize_command_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Убирает внутренний _meta, чтобы в trail оставались только операционные параметры."""
    if not isinstance(params, dict):
        return {}
    return {key: value for key, value in params.items() if key != "_meta"}


async def append_response_audit(
    *,
    trace_id: str,
    stage: str,
    status: str,
    event_type: str = "",
    source_ip: str = "",
    action: str = "",
    command: str = "",
    details: dict[str, Any] | None = None,
    timestamp: int | None = None,
) -> None:
    """Пишет один шаг response trail. В details кладём только компактный, полезный контекст."""
    if not trace_id:
        return
    payload = json.dumps(details or {}, ensure_ascii=False)
    await enqueue_write(
        "INSERT INTO response_audit (timestamp, trace_id, stage, status, event_type, source_ip, action, command, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            int(timestamp or time.time()),
            trace_id,
            stage,
            status,
            event_type,
            source_ip,
            action,
            command,
            payload,
        ),
    )
