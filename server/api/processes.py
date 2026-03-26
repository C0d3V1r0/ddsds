# - API процессов: in-memory снимок от агента
from fastapi import APIRouter

router = APIRouter()

# - Последний снимок процессов, обновляется агентом через WS
_latest_processes: list[dict[str, object]] = []


def update_processes(processes: list[dict[str, object]]) -> None:
    """Обновляет снимок процессов (вызывается из WS-обработчика агента)."""
    global _latest_processes
    _latest_processes = processes


@router.get("/api/processes")
async def get_processes():
    """Возвращает последний снимок процессов."""
    return _latest_processes
