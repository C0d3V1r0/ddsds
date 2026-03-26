# API сервисов: список отслеживаемых сервисов и их статусы
from fastapi import APIRouter
from db import get_db

router = APIRouter()


@router.get("/api/services")
async def get_services():
    """Возвращает список всех сервисов из БД."""
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM services ORDER BY name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()
