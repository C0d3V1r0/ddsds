# Фоновая задача: очистка устаревших данных по retention-политике
import time
import aiosqlite

# Максимальный возраст записей в секундах для каждой таблицы
RETENTION: dict[str, int] = {
    "metrics": 30 * 86400,
    "security_events": 90 * 86400,
    "agent_commands": 30 * 86400,
}

# Захардкоженные запросы для защиты от SQL-инъекции через имя таблицы
_CLEANUP_QUERIES: dict[str, str] = {
    "metrics": "DELETE FROM metrics WHERE timestamp < ?",
    "security_events": "DELETE FROM security_events WHERE timestamp < ?",
    "agent_commands": "DELETE FROM agent_commands WHERE timestamp < ?",
}


async def cleanup_old_data(db_path: str) -> dict[str, int]:
    """Удаляет записи старше retention-порога, возвращает кол-во удалённых по таблицам."""
    now = int(time.time())
    deleted: dict[str, int] = {}

    async with aiosqlite.connect(db_path) as conn:
        for table, max_age in RETENTION.items():
            query = _CLEANUP_QUERIES.get(table)
            if query is None:
                raise ValueError(f"Недопустимое имя таблицы: {table}")
            cutoff = now - max_age
            cursor = await conn.execute(query, (cutoff,))
            deleted[table] = cursor.rowcount
        await conn.commit()

    return deleted
