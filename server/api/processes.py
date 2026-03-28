# API процессов: in-memory снимок от агента
import os

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from security.audit import append_response_audit, make_trace_id

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


async def request_agent_command(
    command: str,
    params: dict,
    *,
    await_result: bool = False,
    timeout: float = 6.0,
):
    """Единая точка отправки команд агенту с поддержкой ожидания результата."""
    from ws.agent import send_command as _send_command
    return await _send_command(command, params, await_result=await_result, timeout=timeout)


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


def _build_process_command_payload(proc: dict[str, object], pid: int) -> dict[str, object]:
    """Собирает минимальный payload, чтобы агент сверил именно тот же процесс."""
    return {
        "pid": pid,
        "expected_name": str(proc.get("name", "")),
        "expected_start_time": int(proc.get("start_time", 0) or 0),
    }


async def _queue_process_command(pid: int, command: str) -> dict[str, object]:
    proc = _find_process(pid)
    if proc is None:
        raise HTTPException(status_code=404, detail="Process not found in current snapshot")
    if is_protected_process(proc):
        raise HTTPException(status_code=403, detail="Protected process cannot be terminated")
    if get_agent_ws() is None:
        raise HTTPException(status_code=503, detail="Agent is not connected")

    trace_id = make_trace_id()
    result = await request_agent_command(
        command,
        {
            **_build_process_command_payload(proc, pid),
            "_meta": {
                "trace_id": trace_id,
                "action": command,
                "origin": "process_api",
            },
        },
        await_result=True,
    )
    if not result or result.get("status") != "success":
        await append_response_audit(
            trace_id=trace_id,
            stage="manual_action",
            status="failed",
            action=command,
            command=command,
            details={"pid": pid, "name": str(proc.get("name", ""))},
        )
        raise HTTPException(status_code=502, detail=str((result or {}).get("error") or "Agent command failed"))
    await append_response_audit(
        trace_id=trace_id,
        stage="manual_action",
        status="success",
        action=command,
        command=command,
        details={"pid": pid, "name": str(proc.get("name", ""))},
    )
    return {
        "status": "success",
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
