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
async def get_logs(source: str = "", limit: int = Query(default=100, ge=1, le=5000)):
    """Возвращает логи с опциональной фильтрацией по источнику."""
    logs = list(_log_buffer)
    if source:
        logs = [log for log in logs if log.get("source") == source]
    return logs[-limit:]
