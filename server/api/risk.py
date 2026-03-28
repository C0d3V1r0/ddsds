# API risk score: сводный риск сервера с объяснимыми факторами
import json
import time
from typing import Iterable

from fastapi import APIRouter, Request

from api import health
from db import enqueue_write, get_db

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


def _normalize_service_name(name: object) -> str:
    return str(name or "").strip().removesuffix(".service")


def _important_stopped_services(
    services: Iterable[dict[str, object]],
    allowed_services: Iterable[str],
) -> list[dict[str, object]]:
    allowed = {_normalize_service_name(name) for name in allowed_services}
    return [
        svc
        for svc in services
        if str(svc.get("status", "")) == "stopped"
        and _normalize_service_name(svc.get("name")) in allowed
    ]


def _group_recent_events(recent_events: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for event in recent_events:
        event_type = str(event.get("type", "")).strip()
        source_ip = str(event.get("source_ip", "")).strip()
        key = (event_type, source_ip)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = {
                "type": event_type,
                "source_ip": source_ip,
                "severity": str(event.get("severity", "")),
                "count": 1,
            }
            continue
        existing["count"] = int(existing.get("count", 1)) + 1
        if _severity_weight(str(event.get("severity", ""))) > _severity_weight(str(existing.get("severity", ""))):
            existing["severity"] = str(event.get("severity", ""))
    return list(grouped.values())


def _event_group_weight(event_group: dict[str, object]) -> int:
    base = _severity_weight(str(event_group.get("severity", "")))
    repeats = max(0, int(event_group.get("count", 1)) - 1)
    # Повторы учитываем мягко: важен сам факт повторения, но без раздувания шума.
    return base + min(4, repeats)


def calculate_risk_score(
    *,
    api_ok: bool,
    agent_connected: bool,
    db_ok: bool,
    latest_metrics_ts: int | None,
    services: Iterable[dict[str, object]],
    recent_events: Iterable[dict[str, object]],
    allowed_services: Iterable[str] = (),
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

    services = list(services)
    failed_services = [svc for svc in services if str(svc.get("status", "")) == "failed"]
    stopped_services = _important_stopped_services(services, allowed_services)
    if failed_services:
        weight = min(30, 10 * len(failed_services))
        score += weight
        factors.append({"code": "failed_services", "weight": weight, "count": len(failed_services)})
    elif stopped_services:
        weight = min(10, 3 * len(stopped_services))
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

    event_groups = _group_recent_events(recent_events)
    event_score = min(25, sum(_event_group_weight(group) for group in event_groups))
    if event_score:
        score += event_score
        factors.append({"code": "recent_security_pressure", "weight": event_score, "count": len(event_groups)})

    score = min(100, score)
    return {
        "score": score,
        "level": _risk_level(score),
        "factors": factors,
        "updated_at": now,
    }


async def build_risk_score_snapshot(request: Request, now: int | None = None) -> dict[str, object]:
    """Собирает текущий риск-скор и возвращает его как единый снапшот."""
    conn = await get_db()
    try:
        effective_now = now or int(time.time())
        allowed_services = tuple(request.app.state.config.security.allowed_services)

        cursor = await conn.execute("SELECT timestamp FROM metrics ORDER BY timestamp DESC LIMIT 1")
        latest_metrics = await cursor.fetchone()
        latest_metrics_ts = int(latest_metrics["timestamp"]) if latest_metrics else None

        cursor = await conn.execute("SELECT name, status FROM services")
        services = [dict(row) for row in await cursor.fetchall()]

        cursor = await conn.execute(
            "SELECT type, severity, source_ip, action_taken FROM security_events WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT 100",
            (effective_now - 900,),
        )
        recent_events = [dict(row) for row in await cursor.fetchall()]

        return calculate_risk_score(
            api_ok=True,
            agent_connected=health._agent_connected,
            db_ok=health._db_ok,
            latest_metrics_ts=latest_metrics_ts,
            services=services,
            recent_events=recent_events,
            allowed_services=allowed_services,
            now=effective_now,
        )
    finally:
        await conn.close()


async def capture_risk_snapshot(request: Request, now: int | None = None) -> dict[str, object]:
    """Сохраняет снапшот риска в историю для трендов и ретроспективы."""
    snapshot = await build_risk_score_snapshot(request, now=now)
    await enqueue_write(
        "INSERT INTO risk_snapshots (timestamp, score, level, factors_json) VALUES (?, ?, ?, ?)",
        (
            int(snapshot["updated_at"]),
            int(snapshot["score"]),
            str(snapshot["level"]),
            json.dumps(snapshot["factors"]),
        ),
    )
    return snapshot


@router.get("/api/risk")
async def get_risk_score(request: Request) -> dict[str, object]:
    return await build_risk_score_snapshot(request)


@router.get("/api/risk/history")
async def get_risk_history(
    request: Request,
    points: int = 24,
) -> list[dict[str, object]]:
    conn = await get_db()
    try:
        max_points = max(6, int(request.app.state.config.risk.history_points))
        effective_points = max(1, min(points, max_points))
        cursor = await conn.execute(
            "SELECT timestamp, score, level, factors_json FROM risk_snapshots ORDER BY timestamp DESC LIMIT ?",
            (effective_points,),
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        history: list[dict[str, object]] = []
        for row in reversed(rows):
            raw_factors = str(row.get("factors_json", "") or "[]")
            try:
                factors = json.loads(raw_factors)
            except json.JSONDecodeError:
                factors = []
            history.append({
                "timestamp": int(row["timestamp"]),
                "score": int(row["score"]),
                "level": str(row["level"]),
                "factors": factors,
            })
        return history
    finally:
        await conn.close()
