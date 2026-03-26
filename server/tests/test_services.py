# Тесты для API сервисов
import pytest
import time
from httpx import AsyncClient, ASGITransport
from db import get_db


@pytest.mark.asyncio
async def test_get_services_empty(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/services")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_services(test_app):
    conn = await get_db()
    await conn.execute(
        "INSERT INTO services (name, status, pid, uptime, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("nginx", "running", 1234, 86400, int(time.time()))
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/services")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "nginx"
    assert data[0]["status"] == "running"
