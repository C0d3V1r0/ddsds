# API risk score: сводный риск сервера с объяснимыми факторами
import time
from typing import Iterable

from fastapi import APIRouter

from api import health
from db import get_db

router = APIRouter()


def _severity_weight(severity: str) -> int:
    return {
        "low": 2,
        "medium": 6,
        "high": 12,
        "critical": 20,
    }.get(severity, 0)


def _risk_level(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def calculate_risk_score(
    *,
    api_ok: bool,
    agent_connected: bool,
    db_ok: bool,
    latest_metrics_ts: int | None,
    services: Iterable[dict[str, object]],
    recent_events: Iterable[dict[str, object]],
    now: int | None = None,
) -> dict[str, object]:
    """Собирает объяснимый риск-скор без ML-магии: только наблюдаемые факторы."""
    now = now or int(time.time())
    factors: list[dict[str, object]] = []
    score = 0

    if not api_ok:
        score += 25
        factors.append({"code": "api_unhealthy", "weight": 25})
    if not agent_connected:
        score += 25
        factors.append({"code": "agent_disconnected", "weight": 25})
    if not db_ok:
        score += 25
        factors.append({"code": "db_unhealthy", "weight": 25})

    failed_services = [svc for svc in services if str(svc.get("status", "")) == "failed"]
    stopped_services = [svc for svc in services if str(svc.get("status", "")) == "stopped"]
    if failed_services:
        weight = min(30, 10 * len(failed_services))
        score += weight
        factors.append({"code": "failed_services", "weight": weight, "count": len(failed_services)})
    elif stopped_services:
        weight = min(15, 5 * len(stopped_services))
        score += weight
        factors.append({"code": "stopped_services", "weight": weight, "count": len(stopped_services)})

    if latest_metrics_ts is None:
        score += 20
        factors.append({"code": "metrics_missing", "weight": 20})
    else:
        age = max(0, now - latest_metrics_ts)
        if age > 300:
            score += 20
            factors.append({"code": "metrics_stale", "weight": 20, "age_seconds": age})
        elif age > 60:
            score += 10
            factors.append({"code": "metrics_aging", "weight": 10, "age_seconds": age})

    event_score = min(35, sum(_severity_weight(str(item.get("severity", ""))) for item in recent_events))
    if event_score:
        score += event_score
        factors.append({"code": "recent_security_pressure", "weight": event_score, "count": len(list(recent_events))})

    score = min(100, score)
    return {
        "score": score,
        "level": _risk_level(score),
        "factors": factors,
        "updated_at": now,
    }


@router.get("/api/risk")
async def get_risk_score() -> dict[str, object]:
    conn = await get_db()
    try:
        now = int(time.time())

        cursor = await conn.execute("SELECT timestamp FROM metrics ORDER BY timestamp DESC LIMIT 1")
        latest_metrics = await cursor.fetchone()
        latest_metrics_ts = int(latest_metrics["timestamp"]) if latest_metrics else None

        cursor = await conn.execute("SELECT name, status FROM services")
        services = [dict(row) for row in await cursor.fetchall()]

        cursor = await conn.execute(
            "SELECT severity FROM security_events WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 100",
            (now - 900,),
        )
        recent_events = [dict(row) for row in await cursor.fetchall()]

        return calculate_risk_score(
            api_ok=True,
            agent_connected=health._agent_connected,
            db_ok=health._db_ok,
            latest_metrics_ts=latest_metrics_ts,
            services=services,
            recent_events=recent_events,
            now=now,
        )
    finally:
        await conn.close()
