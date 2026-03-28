# API логов: in-memory кольцевой буфер от агента
from collections import deque
from fastapi import APIRouter, Query
from security.rules import FIREWALL_LOG_MARKERS, SSH_FAILED_PATTERN, WEB_ATTACK_PATTERNS

router = APIRouter()

# Кольцевой буфер логов, макс. 5000 записей
_log_buffer: deque[dict[str, object]] = deque(maxlen=5000)


def append_log(entry: dict[str, object]) -> None:
    """Добавляет запись лога в буфер (вызывается из WS-обработчика агента)."""
    _log_buffer.append(entry)


def _matches_query(log: dict[str, object], query: str) -> bool:
    if not query:
        return True
    text = str(log.get("line", "")).lower()
    return query.lower() in text


def _matches_ip(log: dict[str, object], ip: str) -> bool:
    if not ip:
        return True
    return ip in str(log.get("line", ""))


def _matches_event_type(log: dict[str, object], event_type: str) -> bool:
    if not event_type:
        return True

    line = str(log.get("line", ""))
    source = str(log.get("source", ""))
    if event_type == "ssh_brute_force":
        return source == "auth" and SSH_FAILED_PATTERN.search(line) is not None
    if event_type in WEB_ATTACK_PATTERNS:
        return source in {"nginx", "apache"} and WEB_ATTACK_PATTERNS[event_type].search(line) is not None
    if event_type == "port_scan":
        return source in {"firewall", "syslog"} and any(marker in line for marker in FIREWALL_LOG_MARKERS)
    return False


@router.get("/api/logs")
async def get_logs(
    source: str = "",
    limit: int = Query(default=100, ge=1, le=5000),
    from_ts: int | None = Query(default=None, ge=0),
    to_ts: int | None = Query(default=None, ge=0),
    q: str = Query(default="", max_length=200),
    ip: str = Query(default="", max_length=64),
    event_type: str = Query(default="", max_length=64),
):
    """Возвращает логи с опциональной фильтрацией по источнику, диапазону и расследовательским признакам."""
    logs = list(_log_buffer)
    if source:
        logs = [log for log in logs if log.get("source") == source]
    if from_ts is not None:
        logs = [log for log in logs if int(log.get("timestamp", 0) or 0) >= from_ts]
    if to_ts is not None:
        logs = [log for log in logs if int(log.get("timestamp", 0) or 0) <= to_ts]
    if q:
        logs = [log for log in logs if _matches_query(log, q)]
    if ip:
        logs = [log for log in logs if _matches_ip(log, ip)]
    if event_type:
        logs = [log for log in logs if _matches_event_type(log, event_type)]
    return logs[-limit:]
