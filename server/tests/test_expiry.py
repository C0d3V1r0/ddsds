# - Тесты expiry: удаление IP с истёкшим сроком блокировки
import pytest
import time
from db import init_db, get_db, start_writer, stop_writer
from tasks.expiry import expire_blocked_ips


@pytest.mark.asyncio
async def test_expire_removes_expired_ips(tmp_path):
    """Истёкшие IP удаляются, активные и бессрочные остаются."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    # - Запускаем writer loop, чтобы enqueue_write реально выполнялся
    writer_task = await start_writer(db_path)

    conn = await get_db()
    now = int(time.time())

    # - IP с истёкшим сроком — должен быть удалён
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, ?)",
        ("10.0.0.1", "test", now - 7200, now - 3600, 1),
    )
    # - IP с активным сроком — должен остаться
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, ?)",
        ("10.0.0.2", "test", now, now + 3600, 1),
    )
    # - Бессрочная блокировка (expires_at=NULL) — должна остаться
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) "
        "VALUES (?, ?, ?, ?)",
        ("10.0.0.3", "permanent", now, 0),
    )
    await conn.commit()
    await conn.close()

    expired = await expire_blocked_ips(db_path)
    assert expired == ["10.0.0.1"]

    # - Останавливаем writer, дожидаясь обработки всех запросов в очереди
    await stop_writer(writer_task)

    conn = await get_db()
    cursor = await conn.execute("SELECT ip FROM blocked_ips ORDER BY ip")
    remaining = [row[0] for row in await cursor.fetchall()]
    await conn.close()

    assert "10.0.0.1" not in remaining
    assert "10.0.0.2" in remaining
    assert "10.0.0.3" in remaining


@pytest.mark.asyncio
async def test_expire_returns_empty_when_no_expired(tmp_path):
    """Если нет истёкших IP — возвращает пустой список."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    conn = await get_db()
    now = int(time.time())

    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, ?)",
        ("10.0.0.5", "test", now, now + 7200, 1),
    )
    await conn.commit()
    await conn.close()

    expired = await expire_blocked_ips(db_path)
    assert expired == []


@pytest.mark.asyncio
async def test_expire_handles_empty_table(tmp_path):
    """Пустая таблица blocked_ips — возвращает пустой список без ошибок."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    expired = await expire_blocked_ips(db_path)
    assert expired == []
