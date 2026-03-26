# Слой работы с SQLite: инициализация, миграции, очередь записи
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional
import aiosqlite

_logger = logging.getLogger("nullius.db")

# Ограничение очереди — защита от переполнения памяти при высокой нагрузке
_write_queue: asyncio.Queue[tuple[Optional[str], tuple[object, ...]]] = asyncio.Queue(maxsize=10000)
_db_path: Optional[str] = None


async def init_db(db_path: str) -> None:
    """Инициализирует БД: включает WAL-режим и применяет миграции."""
    global _db_path
    _db_path = db_path
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await _run_migrations(conn)
        await conn.commit()


async def _run_migrations(conn: aiosqlite.Connection) -> None:
    """Применяет SQL-миграции из директории migrations/ по порядку версий."""
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    cursor = await conn.execute("SELECT version FROM schema_version")
    applied = {row[0] for row in await cursor.fetchall()}

    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        return

    for sql_file in sorted(migrations_dir.glob("*.sql")):
        version = int(sql_file.stem.split("_")[0])
        if version in applied:
            continue
        sql = sql_file.read_text()
        await conn.executescript(sql)
        await conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, int(time.time()))
        )


async def get_db() -> aiosqlite.Connection:
    """Возвращает новое соединение с БД для чтения."""
    if _db_path is None:
        raise RuntimeError("БД не инициализирована, вызовите init_db() сначала")
    conn = await aiosqlite.connect(_db_path)
    conn.row_factory = aiosqlite.Row
    return conn


async def enqueue_write(sql: str, params: tuple[object, ...] = ()) -> None:
    """Помещает запрос на запись в очередь для последовательного выполнения."""
    await _write_queue.put((sql, params))


async def _writer_loop(db_path: str) -> None:
    """Цикл записи: последовательно выполняет запросы из очереди.
    Избегает конкурентных записей в SQLite."""
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA busy_timeout=5000")
            while True:
                sql, params = await _write_queue.get()
                if sql is None:
                    break
                # Три попытки с экспоненциальной задержкой при ошибке
                for attempt in range(3):
                    try:
                        await conn.execute(sql, params)
                        await conn.commit()
                        break
                    except Exception as e:
                        _logger.warning(f"Ошибка записи в БД (попытка {attempt + 1}/3): {e}")
                        if attempt == 2:
                            raise
                        await asyncio.sleep(0.01 * (2 ** attempt))
    except Exception:
        _logger.error("Writer loop завершился с ошибкой", exc_info=True)


async def start_writer(db_path: str) -> asyncio.Task[None]:
    """Запускает фоновую задачу записи."""
    return asyncio.create_task(_writer_loop(db_path))


async def stop_writer(writer_task: asyncio.Task[None]) -> None:
    """Останавливает фоновую задачу записи, дождавшись обработки очереди."""
    await _write_queue.put((None, ()))
    await writer_task
