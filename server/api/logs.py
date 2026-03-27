# API логов: in-memory кольцевой буфер от агента
from collections import deque
from fastapi import APIRouter, Query

router = APIRouter()

# Кольцевой буфер логов, макс. 5000 записей
_log_buffer: deque[dict[str, object]] = deque(maxlen=5000)


def append_log(entry: dict[str, object]) -> None:
    """Добавляет запись лога в буфер (вызывается из WS-обработчика агента)."""
    _log_buffer.append(entry)


@router.get("/api/logs")
async def get_logs(
    source: str = "",
    limit: int = Query(default=100, ge=1, le=5000),
    from_ts: int | None = Query(default=None, ge=0),
    to_ts: int | None = Query(default=None, ge=0),
):
    """Возвращает логи с опциональной фильтрацией по источнику и диапазону времени."""
    logs = list(_log_buffer)
    if source:
        logs = [log for log in logs if log.get("source") == source]
    if from_ts is not None:
        logs = [log for log in logs if int(log.get("timestamp", 0) or 0) >= from_ts]
    if to_ts is not None:
        logs = [log for log in logs if int(log.get("timestamp", 0) or 0) <= to_ts]
    return logs[-limit:]
