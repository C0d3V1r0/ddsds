# Тесты для API метрик (текущие и история)
import pytest
import time
from httpx import AsyncClient, ASGITransport
from db import get_db, enqueue_write

@pytest.mark.asyncio
async def test_get_current_metrics_empty(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics")
    assert resp.status_code == 200
    assert resp.json() is None

@pytest.mark.asyncio
async def test_get_current_metrics(test_app):
    now = int(time.time())
    conn = await get_db()
    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total, ram_used, ram_total) VALUES (?, ?, ?, ?)",
        (now, 45.2, 4096, 8192)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics")
    data = resp.json()
    assert data["cpu_total"] == 45.2
    assert data["ram_used"] == 4096

@pytest.mark.asyncio
async def test_get_metrics_history(test_app):
    now = int(time.time())
    conn = await get_db()
    for i in range(5):
        await conn.execute(
            "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)",
            (now - i * 60, 20.0 + i)
        )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics/history?period=1h")
    data = resp.json()
    assert len(data) == 5
