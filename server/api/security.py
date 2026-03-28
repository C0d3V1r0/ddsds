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
from security.mode import get_operation_mode_state, normalize_operation_mode, set_operation_mode

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


class SecurityModeRequest(BaseModel):
    operation_mode: str

    @field_validator("operation_mode")
    @classmethod
    def validate_operation_mode(cls, value: str) -> str:
        normalized = normalize_operation_mode(value)
        if normalized != value.strip().lower():
            raise ValueError("Invalid operation mode")
        return normalized


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
    elif event_type == "ssh_user_enum":
        signal_source = "rule_auth_logs"
        explanation_code = "ssh_invalid_user_threshold"
        confidence = "medium"
        recommended_action = "review_source_ip"
    elif event_type in {"sqli", "xss", "path_traversal"}:
        signal_source = "rule_web_logs"
        explanation_code = "web_attack_pattern"
        confidence = "high"
        recommended_action = "review_source_ip"
    elif event_type == "sensitive_path_probe":
        signal_source = "rule_web_logs"
        explanation_code = "sensitive_path_probe"
        confidence = "medium"
        recommended_action = "review_related_logs"
    elif event_type == "scanner_probe":
        signal_source = "rule_web_logs"
        explanation_code = "scanner_tool_pattern"
        confidence = "medium"
        recommended_action = "review_related_logs"
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


def _build_suppression_map(rows: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, int]]:
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"suppressed_count": 0, "repeat_count": 0})
    for row in rows:
        event_type = str(row.get("event_type", ""))
        source_key = str(row.get("source_ip", "")).strip() or "host"
        status = str(row.get("status", ""))
        if status == "suppressed":
            grouped[(event_type, source_key)]["suppressed_count"] += 1
            grouped[(event_type, source_key)]["repeat_count"] += 1
        elif status == "suppressed_duplicate":
            grouped[(event_type, source_key)]["repeat_count"] += 1
    return grouped


def _build_incidents(
    rows: list[dict[str, object]],
    suppression_map: dict[tuple[str, str], dict[str, int]] | None = None,
) -> list[dict[str, object]]:
    """Группирует события в лёгкие инциденты без отдельной таблицы и лишней миграции."""
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    enriched_rows = [_enrich_security_event(raw) for raw in rows]
    for event in enriched_rows:
        grouped[_incident_sort_key(event)].append(event)

    now = int(time.time())
    incidents: list[dict[str, object]] = []
    for (event_type, source_key), events in grouped.items():
        events.sort(key=lambda item: int(item.get("timestamp", 0)))
        first = events[0]
        last = events[-1]
        suppression = (suppression_map or {}).get((event_type, source_key), {"suppressed_count": 0, "repeat_count": 0})
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
            "suppressed_count": int(suppression["suppressed_count"]),
            "repeat_count": max(0, len(events) - 1) + int(suppression["repeat_count"]),
            "first_seen": int(first.get("timestamp", 0) or 0),
            "last_seen": int(last.get("timestamp", 0) or 0),
            "latest_event_id": int(last.get("id", 0) or 0),
            "latest_trace_id": str(last.get("trace_id", "") or ""),
            "latest_action_taken": str(last.get("action_taken", "logged") or "logged"),
            "signal_source": str(last.get("signal_source", "generic")),
            "confidence": str(last.get("confidence", "medium")),
            "recommended_action": str(last.get("recommended_action", "review_event")),
            "evidence_types": sorted({str(item.get("type", "")) for item in events}),
            "summary": str(last.get("description", "")),
        })

    incidents.extend(_build_correlated_recon_incidents(enriched_rows))

    incidents.sort(key=lambda item: (int(item["last_seen"]), _severity_rank(str(item["severity"]))), reverse=True)
    return incidents


def _build_correlated_recon_incidents(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Собирает один зрелый recon-инцидент из нескольких слабых сигналов по одному IP.

    Не заменяет исходные события, а даёт оператору более полезную агрегированную картину.
    """
    correlation_window = 900
    recon_types = {"scanner_probe", "sensitive_path_probe", "port_scan", "ssh_user_enum"}
    now = int(time.time())
    by_source: dict[str, list[dict[str, object]]] = defaultdict(list)

    for event in events:
        source_ip = str(event.get("source_ip", "")).strip()
        if not source_ip:
            continue
        if str(event.get("type", "")) not in recon_types:
            continue
        if int(event.get("timestamp", 0) or 0) < now - correlation_window:
            continue
        by_source[source_ip].append(event)

    incidents: list[dict[str, object]] = []
    for source_ip, source_events in by_source.items():
        distinct_types = sorted({str(item.get("type", "")) for item in source_events})
        if len(distinct_types) < 2:
            continue

        source_events.sort(key=lambda item: int(item.get("timestamp", 0) or 0))
        first = source_events[0]
        last = source_events[-1]
        correlated_severity = "high" if "port_scan" in distinct_types and "ssh_user_enum" in distinct_types else "medium"
        incidents.append({
            "id": f"recon_chain:{source_ip}",
            "title": "recon_chain",
            "type": "recon_chain",
            "source_ip": source_ip,
            "severity": correlated_severity,
            "status": "new",
            "event_count": len(source_events),
            "suppressed_count": 0,
            "repeat_count": max(0, len(source_events) - len(distinct_types)),
            "first_seen": int(first.get("timestamp", 0) or 0),
            "last_seen": int(last.get("timestamp", 0) or 0),
            "latest_event_id": int(last.get("id", 0) or 0),
            "latest_trace_id": str(last.get("trace_id", "") or ""),
            "latest_action_taken": str(last.get("action_taken", "logged") or "logged"),
            "signal_source": "generic",
            "confidence": "high" if len(distinct_types) >= 3 else "medium",
            "recommended_action": "review_source_ip" if correlated_severity == "medium" else "auto_block_applied",
            "evidence_types": distinct_types,
            "summary": (
                f"Correlated recon chain: {', '.join(distinct_types)}"
            ),
        })

    return incidents


@router.get("/api/security/events")
async def get_security_events(
    event_type: str = "",
    severity: str = "",
    source_ip: str = "",
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
        if source_ip:
            query += " AND source_ip = ?"
            params.append(source_ip)
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
        min_timestamp = min((int(row.get("timestamp", 0) or 0) for row in rows), default=int(time.time()) - 900)
        cursor = await conn.execute(
            """
            SELECT event_type, source_ip, status
            FROM response_audit
            WHERE timestamp >= ? AND stage = 'decision' AND status IN ('suppressed', 'suppressed_duplicate')
            ORDER BY timestamp DESC
            LIMIT 1000
            """,
            (min_timestamp,),
        )
        suppression_rows = [dict(row) for row in await cursor.fetchall()]
        return _build_incidents(rows, _build_suppression_map(suppression_rows))[:limit]
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


@router.get("/api/security/mode")
async def get_security_mode() -> dict[str, object]:
    return get_operation_mode_state()


@router.post("/api/security/mode")
async def update_security_mode(req: SecurityModeRequest) -> dict[str, object]:
    return await set_operation_mode(req.operation_mode)


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
