# Runtime-режимы работы Nullius: observe, assist, auto_defend.
# Держим это отдельным слоем, чтобы policy менялась сразу и без рестарта API.
import time
from db import enqueue_write, get_db

VALID_OPERATION_MODES = {"observe", "assist", "auto_defend"}

_operation_mode = "auto_defend"
_updated_at = 0


def normalize_operation_mode(value: str) -> str:
    """Нормализует входящее значение и даёт безопасный фолбэк."""
    mode = str(value or "").strip().lower()
    if mode not in VALID_OPERATION_MODES:
        return "auto_defend"
    return mode


def get_operation_mode_state() -> dict[str, object]:
    """Возвращает текущий runtime-режим из памяти."""
    return {
        "operation_mode": _operation_mode,
        "updated_at": _updated_at,
    }


def get_operation_mode() -> str:
    """Короткий helper для policy-слоя."""
    return _operation_mode


async def init_operation_mode(default_mode: str) -> None:
    """Инициализирует runtime-режим из БД или первого значения конфига."""
    global _operation_mode, _updated_at

    normalized_default = normalize_operation_mode(default_mode)
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT operation_mode, updated_at FROM security_runtime_settings WHERE id = 1"
        )
        row = await cursor.fetchone()
    finally:
        await conn.close()

    if row is None:
        _operation_mode = normalized_default
        _updated_at = int(time.time())
        await enqueue_write(
            "INSERT OR REPLACE INTO security_runtime_settings (id, operation_mode, updated_at) VALUES (1, ?, ?)",
            (_operation_mode, _updated_at),
        )
        return

    stored_updated_at = int(row["updated_at"] or 0)
    if stored_updated_at <= 0:
        _operation_mode = normalized_default
        _updated_at = int(time.time())
        await enqueue_write(
            "INSERT OR REPLACE INTO security_runtime_settings (id, operation_mode, updated_at) VALUES (1, ?, ?)",
            (_operation_mode, _updated_at),
        )
        return

    _operation_mode = normalize_operation_mode(str(row["operation_mode"] or normalized_default))
    _updated_at = stored_updated_at


async def set_operation_mode(mode: str) -> dict[str, object]:
    """Меняет runtime-режим и сохраняет его в БД."""
    global _operation_mode, _updated_at

    _operation_mode = normalize_operation_mode(mode)
    _updated_at = int(time.time())
    await enqueue_write(
        "INSERT OR REPLACE INTO security_runtime_settings (id, operation_mode, updated_at) VALUES (1, ?, ?)",
        (_operation_mode, _updated_at),
    )
    return get_operation_mode_state()
