# - API метрик: текущее состояние и история
import time
from fastapi import APIRouter, HTTPException
from db import get_db

router = APIRouter()

# - Маппинг строковых периодов в секунды
PERIOD_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
}


@router.get("/api/metrics")
async def get_current_metrics():
    """Возвращает последнюю запись метрик или None."""
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM metrics ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        await conn.close()


@router.get("/api/metrics/history")
async def get_metrics_history(period: str = "1h"):
    """- Возвращает метрики за указанный период."""
    if period not in PERIOD_SECONDS:
        raise HTTPException(status_code=400, detail=f"Invalid period. Allowed: {', '.join(PERIOD_SECONDS)}")
    seconds = PERIOD_SECONDS[period]
    since = int(time.time()) - seconds
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM metrics WHERE timestamp >= ? ORDER BY timestamp ASC",
            (since,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()
