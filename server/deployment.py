# Runtime-состояние режима развёртывания: primary или standby.
# Это не "полный HA", а честный первый шаг к warm standby без опасной магии.
import fcntl
import json
import os
import time
from pathlib import Path


_deployment_role = "primary"
_node_name = ""
_primary_lock_path = ""
_updated_at = 0
_primary_lock_fd = None


def normalize_deployment_role(value: str) -> str:
    """Нормализует роль узла и не даёт разрастись произвольным строкам."""
    normalized = str(value or "").strip().lower()
    if normalized not in {"primary", "standby"}:
        raise ValueError("Invalid deployment role")
    return normalized


def release_primary_lock() -> None:
    global _primary_lock_fd
    if _primary_lock_fd is None:
        return
    try:
        fcntl.flock(_primary_lock_fd.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        _primary_lock_fd.close()
    except OSError:
        pass
    _primary_lock_fd = None


def _read_lock_payload(lock_path: str) -> dict[str, object]:
    lock_file = Path(lock_path)
    if not lock_file.exists():
        return {}
    try:
        payload = json.loads(lock_file.read_text(encoding="utf-8").strip() or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def inspect_primary_lock(lock_path: str) -> dict[str, object]:
    """Читает lock metadata и пытается понять, удерживается ли lock прямо сейчас."""
    lock_file = Path(lock_path)
    payload = _read_lock_payload(lock_path)
    if not lock_file.exists():
        return {
            "path": lock_path,
            "exists": False,
            "locked": False,
            "owner_node_name": "",
            "owner_pid": 0,
            "updated_at": 0,
        }

    fd = open(lock_file, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            locked = True
        else:
            locked = False
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
    finally:
        fd.close()

    return {
        "path": lock_path,
        "exists": True,
        "locked": locked,
        "owner_node_name": str(payload.get("node_name", "") or ""),
        "owner_pid": int(payload.get("pid", 0) or 0),
        "updated_at": int(payload.get("updated_at", 0) or 0),
    }


def _acquire_primary_lock(node_name: str, lock_path: str) -> None:
    global _primary_lock_fd

    lock_file = Path(lock_path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_file, "a+", encoding="utf-8")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fd.close()
        raise RuntimeError(
            f"Primary lock already held for {lock_path}. Refusing to start another primary node."
        ) from exc

    payload = {
        "node_name": node_name,
        "role": "primary",
        "pid": os.getpid(),
        "updated_at": int(time.time()),
    }
    fd.seek(0)
    fd.truncate()
    fd.write(json.dumps(payload, ensure_ascii=False))
    fd.flush()
    os.fsync(fd.fileno())
    _primary_lock_fd = fd


def init_deployment_role(role: str, node_name: str, primary_lock_path: str) -> dict[str, object]:
    """Инициализирует роль узла при старте приложения."""
    global _deployment_role, _node_name, _primary_lock_path, _updated_at

    _deployment_role = normalize_deployment_role(role)
    _node_name = str(node_name or "").strip() or "nullius-node"
    _primary_lock_path = str(primary_lock_path or "").strip()
    _updated_at = int(time.time())
    release_primary_lock()
    if _deployment_role == "primary":
        _acquire_primary_lock(_node_name, _primary_lock_path)
    return get_deployment_state()


def is_primary_role() -> bool:
    return _deployment_role == "primary"


def background_tasks_enabled() -> bool:
    """Фоновые mutating-циклы должны жить только на primary."""
    return is_primary_role()


def active_response_enabled() -> bool:
    """Standby может наблюдать, но не должен выполнять активные действия."""
    return is_primary_role()


def get_deployment_state() -> dict[str, object]:
    role = _deployment_role
    lock_info = inspect_primary_lock(_primary_lock_path) if _primary_lock_path else {
        "path": "",
        "exists": False,
        "locked": False,
        "owner_node_name": "",
        "owner_pid": 0,
        "updated_at": 0,
    }
    return {
        "role": role,
        "node_name": _node_name,
        "primary_lock_path": _primary_lock_path,
        "updated_at": _updated_at,
        "background_tasks_enabled": background_tasks_enabled(),
        "active_response_enabled": active_response_enabled(),
        "promote_supported": role == "standby",
        "primary_lock_held": _primary_lock_fd is not None,
        "primary_lock_info": lock_info,
    }
