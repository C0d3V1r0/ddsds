# API процессов: in-memory снимок от агента
import os

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Последний снимок процессов, обновляется агентом через WS
_latest_processes: list[dict[str, object]] = []
MAX_PROCESS_SNAPSHOT = 2000
PROTECTED_PROCESS_NAMES = {
    "nullius-agent",
    "nullius-api",
    "sshd",
    "systemd",
    "systemd-journald",
    "systemd-logind",
    "nginx",
}


class ProcessActionRequest(BaseModel):
    pid: int = Field(..., gt=0)


def get_agent_ws():
    from ws.agent import get_agent_ws as _get_agent_ws
    return _get_agent_ws()


async def send_command(command: str, params: dict) -> None:
    from ws.agent import send_command as _send_command
    await _send_command(command, params)


def _find_process(pid: int) -> dict[str, object] | None:
    for proc in _latest_processes:
        if proc.get("pid") == pid:
            return proc
    return None


def is_protected_process(proc: dict[str, object] | None) -> bool:
    if not proc:
        return True
    pid = int(proc.get("pid", 0) or 0)
    if pid <= 0 or pid == os.getpid():
        return True
    name = str(proc.get("name", "")).strip()
    if not name:
        return True
    if name in PROTECTED_PROCESS_NAMES:
        return True
    if name.startswith("systemd-") or name.startswith("kworker"):
        return True
    return False


def update_processes(processes: list[dict[str, object]]) -> None:
    """Обновляет снимок процессов (вызывается из WS-обработчика агента)."""
    global _latest_processes
    _latest_processes = list(processes[:MAX_PROCESS_SNAPSHOT])


async def _queue_process_command(pid: int, command: str) -> dict[str, object]:
    proc = _find_process(pid)
    if proc is None:
        raise HTTPException(status_code=404, detail="Process not found in current snapshot")
    if is_protected_process(proc):
        raise HTTPException(status_code=403, detail="Protected process cannot be terminated")
    if get_agent_ws() is None:
        raise HTTPException(status_code=503, detail="Agent is not connected")

    await send_command(command, {"pid": pid})
    return {
        "status": "queued",
        "pid": pid,
        "name": proc.get("name", ""),
    }


@router.get("/api/processes")
async def get_processes():
    """Возвращает последний снимок процессов."""
    return _latest_processes


@router.post("/api/processes/terminate")
async def terminate_process(req: ProcessActionRequest):
    """Отправляет агенту команду на graceful terminate процесса по PID."""
    return await _queue_process_command(req.pid, "kill_process")


@router.post("/api/processes/force-kill")
async def force_kill_process(req: ProcessActionRequest):
    """Отправляет агенту команду на немедленный SIGKILL процесса по PID."""
    return await _queue_process_command(req.pid, "force_kill_process")
