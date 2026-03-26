# - Эндпоинт проверки состояния сервера
from fastapi import APIRouter

router = APIRouter()

# - Состояние устанавливается из main.py при старте
_agent_connected = False
_db_ok = False


def set_agent_status(connected: bool) -> None:
    global _agent_connected
    _agent_connected = connected


def set_db_status(ok: bool) -> None:
    global _db_ok
    _db_ok = ok


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "agent": "connected" if _agent_connected else "disconnected",
        "db": "ok" if _db_ok else "error",
    }
