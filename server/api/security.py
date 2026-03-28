# REST API для событий безопасности и управления блокировкой IP
import ipaddress
import json
import time
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator
from db import get_db, enqueue_write
from security.audit import append_response_audit, make_trace_id

router = APIRouter()
MAX_BLOCK_DURATION = 30 * 86400


class BlockRequest(BaseModel):
    ip: str
    reason: str = Field(default="", max_length=500)
    duration: Optional[int] = Field(default=None, ge=60, le=MAX_BLOCK_DURATION)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        ip = value.strip()
        if not _validate_ip(ip):
            raise ValueError("Invalid IP address format")
        return ip

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class UnblockRequest(BaseModel):
    ip: str

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        ip = value.strip()
        if not _validate_ip(ip):
            raise ValueError("Invalid IP address format")
        return ip


def _validate_ip(ip: str) -> bool:
    """Проверяет формат IPv4/IPv6 через стандартную библиотеку."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _enrich_security_event(row: dict[str, object]) -> dict[str, object]:
    """Добавляет explainable-поля, чтобы UI показывал не только факт события, но и его смысл."""
    event = dict(row)
    event_type = str(event.get("type", ""))
    action_taken = str(event.get("action_taken", "logged"))
    description = str(event.get("description", ""))

    signal_source = "generic"
    explanation_code = "generic_event"
    confidence = "medium"
    recommended_action = "review_event"
    is_rule_plus_ml = description.startswith("Rule+ML confirmed:")
    is_ml_detection = description.startswith("ML-detected:")

    if event_type == "anomaly":
        signal_source = "ml_metrics_detector"
        explanation_code = "metrics_anomaly"
        confidence = "medium"
        recommended_action = "review_host_metrics"
    elif is_rule_plus_ml:
        signal_source = "rule_plus_ml"
        explanation_code = "rule_ml_confirmed"
        confidence = "high"
        recommended_action = "review_source_ip" if event_type != "anomaly" else "review_host_metrics"
    elif is_ml_detection:
        if event_type == "ssh_brute_force":
            signal_source = "ml_log_classifier"
            explanation_code = "ml_log_classifier"
            confidence = "medium"
            recommended_action = "review_related_logs"
        else:
            signal_source = "ml_log_classifier"
            explanation_code = "ml_log_classifier"
            confidence = "medium"
            recommended_action = "review_related_logs"
    elif event_type == "ssh_brute_force":
        signal_source = "rule_auth_logs"
        explanation_code = "ssh_failed_attempts_threshold"
        confidence = "high"
        recommended_action = "review_source_ip"
    elif event_type in {"sqli", "xss", "path_traversal"}:
        signal_source = "rule_web_logs"
        explanation_code = "web_attack_pattern"
        confidence = "high"
        recommended_action = "review_source_ip"
    elif event_type == "port_scan":
        signal_source = "rule_firewall_logs"
        explanation_code = "unique_destination_ports_threshold"
        confidence = "medium"
        recommended_action = "review_source_ip"

    if action_taken == "auto_block":
        recommended_action = "auto_block_applied"
    elif action_taken == "logged":
        recommended_action = "monitor_only"

    event["signal_source"] = signal_source
    event["explanation_code"] = explanation_code
    event["confidence"] = confidence
    event["recommended_action"] = recommended_action
    return event


def _incident_sort_key(event: dict[str, object]) -> tuple[str, str]:
    source = str(event.get("source_ip", "")).strip() or "host"
    return str(event.get("type", "")), source


def _severity_rank(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(value, 0)


def _build_incidents(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Группирует события в лёгкие инциденты без отдельной таблицы и лишней миграции."""
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for raw in rows:
        event = _enrich_security_event(raw)
        grouped[_incident_sort_key(event)].append(event)

    now = int(time.time())
    incidents: list[dict[str, object]] = []
    for (event_type, source_key), events in grouped.items():
        events.sort(key=lambda item: int(item.get("timestamp", 0)))
        first = events[0]
        last = events[-1]
        severity = max((str(item.get("severity", "low")) for item in events), key=_severity_rank, default="low")
        all_resolved = all(int(item.get("resolved", 0) or 0) == 1 for item in events)
        if all_resolved:
            status = "resolved"
        elif int(last.get("timestamp", 0) or 0) >= now - 900:
            status = "new"
        else:
            status = "investigating"

        incidents.append({
            "id": f"{event_type}:{source_key}",
            "title": first.get("type", ""),
            "type": event_type,
            "source_ip": "" if source_key == "host" else source_key,
            "severity": severity,
            "status": status,
            "event_count": len(events),
            "first_seen": int(first.get("timestamp", 0) or 0),
            "last_seen": int(last.get("timestamp", 0) or 0),
            "latest_event_id": int(last.get("id", 0) or 0),
            "latest_trace_id": str(last.get("trace_id", "") or ""),
            "signal_source": str(last.get("signal_source", "generic")),
            "confidence": str(last.get("confidence", "medium")),
            "recommended_action": str(last.get("recommended_action", "review_event")),
            "summary": str(last.get("description", "")),
        })

    incidents.sort(key=lambda item: (int(item["last_seen"]), _severity_rank(str(item["severity"]))), reverse=True)
    return incidents


@router.get("/api/security/events")
async def get_security_events(
    event_type: str = "",
    severity: str = "",
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, object]]:
    conn = await get_db()
    try:
        query = "SELECT * FROM security_events WHERE 1=1"
        params: list[object] = []
        if event_type:
            query += " AND type = ?"
            params.append(event_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [_enrich_security_event(dict(row)) for row in rows]
    finally:
        await conn.close()


@router.get("/api/security/incidents")
async def get_security_incidents(
    event_type: str = "",
    limit: int = Query(default=20, ge=1, le=200),
) -> list[dict[str, object]]:
    conn = await get_db()
    try:
        query = "SELECT * FROM security_events WHERE 1=1"
        params: list[object] = []
        if event_type:
            query += " AND type = ?"
            params.append(event_type)
        # Для лёгкого incident center берём недавнее окно, чтобы не тащить весь архив.
        query += " ORDER BY timestamp DESC LIMIT 500"
        cursor = await conn.execute(query, params)
        rows = [dict(row) for row in await cursor.fetchall()]
        return _build_incidents(rows)[:limit]
    finally:
        await conn.close()


@router.get("/api/security/audit")
async def get_response_audit(
    trace_id: str = "",
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, object]]:
    conn = await get_db()
    try:
        query = "SELECT * FROM response_audit WHERE 1=1"
        params: list[object] = []
        if trace_id:
            query += " AND trace_id = ?"
            params.append(trace_id)
        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)
        cursor = await conn.execute(query, params)
        rows = [dict(row) for row in await cursor.fetchall()]
        for row in rows:
            raw_details = row.get("details", "")
            if isinstance(raw_details, str) and raw_details:
                try:
                    row["details"] = json.loads(raw_details)
                except json.JSONDecodeError:
                    row["details"] = {}
            else:
                row["details"] = {}
        return rows
    finally:
        await conn.close()


@router.get("/api/security/blocked")
async def get_blocked_ips() -> list[dict[str, object]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM blocked_ips ORDER BY blocked_at DESC LIMIT 1000"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


@router.post("/api/security/block")
async def block_ip(req: BlockRequest) -> dict[str, str]:
    now = int(time.time())
    expires = now + req.duration if req.duration else None
    trace_id = make_trace_id()
    await append_response_audit(
        trace_id=trace_id,
        stage="manual_action",
        status="blocked",
        source_ip=req.ip,
        action="manual_block",
        details={
            "reason": req.reason,
            "duration": req.duration,
        },
        timestamp=now,
    )
    # Запись через очередь — не блокируем БД конкурентными записями
    await enqueue_write(
        "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, 0)",
        (req.ip, req.reason, now, expires),
    )
    return {"status": "blocked", "ip": req.ip}


@router.post("/api/security/unblock")
async def unblock_ip(req: UnblockRequest) -> dict[str, str]:
    await append_response_audit(
        trace_id=make_trace_id(),
        stage="manual_action",
        status="unblocked",
        source_ip=req.ip,
        action="manual_unblock",
        timestamp=int(time.time()),
    )
    await enqueue_write("DELETE FROM blocked_ips WHERE ip = ?", (req.ip,))
    return {"status": "unblocked", "ip": req.ip}
