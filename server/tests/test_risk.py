import time

import pytest
from httpx import ASGITransport, AsyncClient

from api import health
from api.risk import calculate_risk_score
from db import get_db


def test_calculate_risk_score_low_when_everything_is_healthy():
    result = calculate_risk_score(
        api_ok=True,
        agent_connected=True,
        db_ok=True,
        latest_metrics_ts=int(time.time()),
        services=[{"name": "nginx", "status": "running"}],
        recent_events=[],
        allowed_services=["nginx"],
        now=int(time.time()),
    )
    assert result["level"] == "low"
    assert result["score"] == 0


def test_calculate_risk_score_escalates_with_failures():
    now = int(time.time())
    result = calculate_risk_score(
        api_ok=True,
        agent_connected=False,
        db_ok=True,
        latest_metrics_ts=now - 600,
        services=[{"name": "nginx", "status": "failed"}],
        recent_events=[{"severity": "high"}, {"severity": "medium"}],
        allowed_services=["nginx"],
        now=now,
    )
    assert result["score"] >= 50
    assert result["level"] in {"high", "critical"}
    assert any(factor["code"] == "agent_disconnected" for factor in result["factors"])


def test_calculate_risk_score_ignores_non_critical_stopped_services_and_deduplicates_event_pressure():
    now = int(time.time())
    result = calculate_risk_score(
        api_ok=True,
        agent_connected=True,
        db_ok=True,
        latest_metrics_ts=now,
        services=[
            {"name": "nginx", "status": "running"},
            {"name": "bluetooth", "status": "stopped"},
            {"name": "cups", "status": "stopped"},
            {"name": "postgresql", "status": "stopped"},
        ],
        recent_events=[
            {"type": "port_scan", "severity": "medium", "source_ip": "10.0.0.9", "action_taken": "review_required"},
            {"type": "port_scan", "severity": "medium", "source_ip": "10.0.0.9", "action_taken": "review_required"},
            {"type": "port_scan", "severity": "medium", "source_ip": "10.0.0.9", "action_taken": "review_required"},
        ],
        allowed_services=["nginx", "postgresql"],
        now=now,
    )
    stopped_factor = next((factor for factor in result["factors"] if factor["code"] == "stopped_services"), None)
    pressure_factor = next((factor for factor in result["factors"] if factor["code"] == "recent_security_pressure"), None)

    assert stopped_factor is not None
    assert stopped_factor["count"] == 1
    assert stopped_factor["weight"] == 3
    assert pressure_factor is not None
    assert pressure_factor["count"] == 1
    assert pressure_factor["weight"] < 18


@pytest.mark.asyncio
async def test_get_risk_score_returns_payload(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total, cpu_cores, ram_used, ram_total, network_rx, network_tx, load_avg, disk) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now, 10.0, "[]", 100, 200, 1, 1, "[]", "[]"),
    )
    await conn.execute(
        "INSERT OR REPLACE INTO services (name, status, pid, uptime, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("nginx", "running", 123, 100, now),
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, action_taken) VALUES (?, ?, ?, ?, ?, ?)",
        (now, "path_traversal", "medium", "10.0.0.9", "path_traversal pattern detected", "review_required"),
    )
    await conn.commit()
    await conn.close()

    health.set_agent_status(True)
    health.set_db_status(True)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/risk")

    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "level" in data
    assert "factors" in data


@pytest.mark.asyncio
async def test_get_risk_history_returns_recent_snapshots(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO risk_snapshots (timestamp, score, level, factors_json) VALUES (?, ?, ?, ?)",
        (now - 300, 12, "low", "[]"),
    )
    await conn.execute(
        "INSERT INTO risk_snapshots (timestamp, score, level, factors_json) VALUES (?, ?, ?, ?)",
        (now, 28, "medium", '[{"code":"recent_security_pressure","weight":12,"count":2}]'),
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/risk/history?points=2")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["score"] == 12
    assert data[1]["score"] == 28
    assert data[1]["factors"][0]["code"] == "recent_security_pressure"
