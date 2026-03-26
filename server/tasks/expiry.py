# - Фоновая задача: удаление заблокированных IP с истёкшим сроком
import time
import aiosqlite
from db import enqueue_write


async def expire_blocked_ips(db_path: str) -> list[str]:
    """Удаляет IP с истёкшим expires_at, возвращает список удалённых адресов."""
    now = int(time.time())

    # - SELECT через прямое соединение — enqueue_write не возвращает результат
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT ip FROM blocked_ips WHERE expires_at IS NOT NULL "
            "AND expires_at > 0 AND expires_at < ?",
            (now,),
        )
        expired = [row[0] for row in await cursor.fetchall()]

    if expired:
        placeholders = ",".join("?" * len(expired))
        # - DELETE через очередь записи для консистентности
        await enqueue_write(
            f"DELETE FROM blocked_ips WHERE ip IN ({placeholders})",
            tuple(expired),
        )

    return expired
