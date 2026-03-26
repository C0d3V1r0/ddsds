# - Тесты retention: очистка устаревших метрик, событий, команд
import pytest
import time
from db import init_db, get_db
from tasks.retention import cleanup_old_data


@pytest.mark.asyncio
async def test_cleanup_removes_old_metrics(tmp_path):
    """Старые метрики удаляются, свежие остаются."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    conn = await get_db()
    now = int(time.time())
    old = now - 31 * 86400

    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)", (old, 10.0)
    )
    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)", (now, 20.0)
    )
    await conn.commit()
    await conn.close()

    deleted = await cleanup_old_data(db_path)
    assert deleted["metrics"] == 1

    conn = await get_db()
    cursor = await conn.execute("SELECT COUNT(*) FROM metrics")
    count = (await cursor.fetchone())[0]
    await conn.close()
    assert count == 1


@pytest.mark.asyncio
async def test_cleanup_removes_old_security_events(tmp_path):
    """События безопасности старше 90 дней удаляются."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    conn = await get_db()
    now = int(time.time())
    old = now - 91 * 86400

    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, description) "
        "VALUES (?, ?, ?, ?)",
        (old, "brute_force", "high", "old event"),
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, description) "
        "VALUES (?, ?, ?, ?)",
        (now, "brute_force", "high", "fresh event"),
    )
    await conn.commit()
    await conn.close()

    deleted = await cleanup_old_data(db_path)
    assert deleted["security_events"] == 1

    conn = await get_db()
    cursor = await conn.execute("SELECT COUNT(*) FROM security_events")
    count = (await cursor.fetchone())[0]
    await conn.close()
    assert count == 1


@pytest.mark.asyncio
async def test_cleanup_keeps_recent_data(tmp_path):
    """Если все записи свежие — ничего не удаляется."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    conn = await get_db()
    now = int(time.time())

    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)", (now, 50.0)
    )
    await conn.execute(
        "INSERT INTO agent_commands (timestamp, command) VALUES (?, ?)",
        (now, "status"),
    )
    await conn.commit()
    await conn.close()

    deleted = await cleanup_old_data(db_path)
    assert deleted["metrics"] == 0
    assert deleted["agent_commands"] == 0
