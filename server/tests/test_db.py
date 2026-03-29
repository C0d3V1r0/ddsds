import pytest
import pytest_asyncio
import aiosqlite
from db import init_db, enqueue_write, start_writer, stop_writer


@pytest_asyncio.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await init_db(path)
    return path


@pytest.mark.asyncio
async def test_init_db_creates_tables(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
    assert "metrics" in tables
    assert "security_events" in tables
    assert "blocked_ips" in tables
    assert "services" in tables
    assert "ml_models" in tables
    assert "agent_commands" in tables
    assert "response_audit" in tables
    assert "schema_version" in tables


@pytest.mark.asyncio
async def test_init_db_wal_mode(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA journal_mode")
        mode = (await cursor.fetchone())[0]
    assert mode == "wal"


@pytest.mark.asyncio
async def test_schema_version_recorded(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT version FROM schema_version")
        versions = [row[0] for row in await cursor.fetchall()]
    assert 1 in versions
    assert 2 in versions
    assert 3 in versions


@pytest.mark.asyncio
async def test_write_queue(db_path):
    writer_task = await start_writer(db_path)
    await enqueue_write(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)",
        (1000, 23.5)
    )
    await stop_writer(writer_task)
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT cpu_total FROM metrics WHERE timestamp = 1000")
        row = await cursor.fetchone()
    assert row[0] == 23.5
