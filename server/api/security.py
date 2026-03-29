# REST API для событий безопасности и управления блокировкой IP
import ipaddress
import json
import time
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from deployment import is_primary_role
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


class IncidentStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"new", "investigating", "resolved"}:
            raise ValueError("Invalid incident status")
        return normalized


class IncidentNoteRequest(BaseModel):
    note: str = Field(min_length=1, max_length=1000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


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
    elif event_type in {"sqli", "xss", "path_traversal", "command_injection"}:
        signal_source = "rule_web_logs"
        explanation_code = "web_attack_pattern"
        confidence = "high"
        recommended_action = "review_source_ip"
    elif event_type == "web_login_bruteforce":
        signal_source = "rule_web_logs"
        explanation_code = "web_login_threshold"
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


def _split_incident_id(incident_id: str) -> tuple[str, str]:
    incident_type, _, source_key = str(incident_id or "").partition(":")
    return incident_type, source_key


def _is_derived_incident(incident_type: str) -> bool:
    return incident_type in {"recon_chain", "credential_attack_chain", "web_attack_chain"}


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


def _deserialize_audit_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    deserialized: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        raw_details = item.get("details", "")
        if isinstance(raw_details, str) and raw_details:
            try:
                item["details"] = json.loads(raw_details)
            except json.JSONDecodeError:
                item["details"] = {}
        else:
            item["details"] = {}
        deserialized.append(item)
    return deserialized


async def _load_recent_security_rows(conn, event_type: str = "", limit: int = 500) -> list[dict[str, object]]:
    query = "SELECT * FROM security_events WHERE 1=1"
    params: list[object] = []
    if event_type:
        query += " AND type = ?"
        params.append(event_type)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    cursor = await conn.execute(query, params)
    return [dict(row) for row in await cursor.fetchall()]


async def _load_incident_catalog(conn, event_type: str = "", limit: int = 20) -> list[dict[str, object]]:
    rows = await _load_recent_security_rows(conn, event_type)
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
    incidents = _build_incidents(rows, _build_suppression_map(suppression_rows))[:limit]
    incident_ids = [str(item["id"]) for item in incidents]
    incident_state = await _load_incident_state(conn, incident_ids)
    note_counts = await _load_incident_note_counts(conn, incident_ids)
    return _apply_incident_workflow(incidents, incident_state, note_counts)


def _make_progression_step(event: dict[str, object]) -> dict[str, object]:
    return {
        "timestamp": int(event.get("timestamp", 0) or 0),
        "type": str(event.get("type", "") or ""),
        "severity": str(event.get("severity", "low") or "low"),
        "action_taken": str(event.get("action_taken", "logged") or "logged"),
        "description": str(event.get("description", "") or ""),
    }


def _build_incident_resolution_summary(
    incident: dict[str, object],
    blocked_row: dict[str, object] | None,
    notes: list[dict[str, object]],
    audit_rows: list[dict[str, object]],
) -> dict[str, object]:
    last_note = notes[0] if notes else None
    last_audit = audit_rows[0] if audit_rows else None
    status = str(incident.get("status", "new"))

    if status == "resolved":
        return {
            "state": "resolved",
            "headline": "incident_resolved",
            "note": str(last_note.get("note", "") if last_note else ""),
            "updated_at": int(incident.get("status_updated_at", 0) or 0),
        }
    if blocked_row:
        return {
            "state": "contained",
            "headline": "source_blocked",
            "note": str(blocked_row.get("reason", "") or ""),
            "updated_at": int(blocked_row.get("blocked_at", 0) or 0),
        }
    if last_audit and str(last_audit.get("stage", "")) == "decision":
        details = last_audit.get("details", {})
        return {
            "state": "decision_recorded",
            "headline": str(details.get("policy_stage", "review") or "review"),
            "note": str(details.get("reason", "") or ""),
            "updated_at": int(last_audit.get("timestamp", 0) or 0),
        }
    return {
        "state": "open",
        "headline": "investigation_open",
        "note": "",
        "updated_at": int(incident.get("last_seen", 0) or 0),
    }


async def _load_incident_detail(conn, incident_id: str) -> dict[str, object]:
    incidents = await _load_incident_catalog(conn, limit=200)
    incident = next((item for item in incidents if str(item["id"]) == incident_id), None)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident_type, source_key = _split_incident_id(incident_id)
    source_ip = "" if source_key == "host" else source_key
    evidence_types = {str(item) for item in incident.get("evidence_types", [])}
    timeline_window_start = int(incident.get("first_seen", 0) or 0) - 60
    timeline_window_end = int(incident.get("last_seen", 0) or 0) + 60

    related_query = "SELECT * FROM security_events WHERE timestamp BETWEEN ? AND ?"
    related_params: list[object] = [timeline_window_start, timeline_window_end]
    if source_ip:
        related_query += " AND source_ip = ?"
        related_params.append(source_ip)
    else:
        related_query += " AND (source_ip = '' OR source_ip IS NULL)"

    if _is_derived_incident(incident_type):
        if evidence_types:
            placeholders = ",".join("?" for _ in evidence_types)
            related_query += f" AND type IN ({placeholders})"
            related_params.extend(sorted(evidence_types))
    else:
        related_query += " AND type = ?"
        related_params.append(incident_type)

    related_query += " ORDER BY timestamp ASC, id ASC LIMIT 50"
    cursor = await conn.execute(related_query, tuple(related_params))
    related_events = [_enrich_security_event(dict(row)) for row in await cursor.fetchall()]

    cursor = await conn.execute(
        """
        SELECT id, incident_id, incident_type, source_ip, note, status_at_time, created_at
        FROM incident_notes
        WHERE incident_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 10
        """,
        (incident_id,),
    )
    notes = [dict(row) for row in await cursor.fetchall()]

    blocked_row = None
    if source_ip:
        cursor = await conn.execute(
            "SELECT ip, reason, blocked_at, expires_at, auto FROM blocked_ips WHERE ip = ?",
            (source_ip,),
        )
        row = await cursor.fetchone()
        blocked_row = dict(row) if row else None

    audit_rows: list[dict[str, object]] = []
    latest_trace_id = str(incident.get("latest_trace_id", "") or "")
    if latest_trace_id:
        cursor = await conn.execute(
            "SELECT * FROM response_audit WHERE trace_id = ? ORDER BY timestamp DESC, id DESC LIMIT 20",
            (latest_trace_id,),
        )
        audit_rows = _deserialize_audit_rows([dict(row) for row in await cursor.fetchall()])

    evidence_summary = [
        {"type": event_type, "count": sum(1 for item in related_events if str(item.get("type", "")) == event_type)}
        for event_type in sorted(evidence_types)
    ]

    return {
        "incident": incident,
        "related_events": related_events,
        "blocked_ip": blocked_row,
        "audit_entries": audit_rows,
        "notes": notes,
        "progression": [_make_progression_step(event) for event in related_events],
        "evidence_summary": evidence_summary,
        "resolution_summary": _build_incident_resolution_summary(incident, blocked_row, notes, audit_rows),
    }


async def _load_incident_state(conn, incident_ids: list[str]) -> dict[str, dict[str, object]]:
    if not incident_ids:
        return {}

    placeholders = ",".join("?" for _ in incident_ids)
    cursor = await conn.execute(
        f"SELECT incident_id, status, updated_at FROM incident_state WHERE incident_id IN ({placeholders})",
        tuple(incident_ids),
    )
    return {
        str(row["incident_id"]): {
            "status": str(row["status"] or "new"),
            "updated_at": int(row["updated_at"] or 0),
        }
        for row in await cursor.fetchall()
    }


async def _load_incident_note_counts(conn, incident_ids: list[str]) -> dict[str, int]:
    if not incident_ids:
        return {}

    placeholders = ",".join("?" for _ in incident_ids)
    cursor = await conn.execute(
        f"""
        SELECT incident_id, COUNT(*) AS note_count
        FROM incident_notes
        WHERE incident_id IN ({placeholders})
        GROUP BY incident_id
        """,
        tuple(incident_ids),
    )
    return {str(row["incident_id"]): int(row["note_count"] or 0) for row in await cursor.fetchall()}


def _apply_incident_workflow(
    incidents: list[dict[str, object]],
    incident_state: dict[str, dict[str, object]],
    note_counts: dict[str, int],
) -> list[dict[str, object]]:
    hydrated: list[dict[str, object]] = []
    for incident in incidents:
        hydrated_incident = dict(incident)
        state = incident_state.get(str(incident["id"]))
        if state:
            hydrated_incident["status"] = str(state["status"])
            hydrated_incident["status_updated_at"] = int(state["updated_at"])
        else:
            hydrated_incident["status_updated_at"] = 0
        hydrated_incident["note_count"] = int(note_counts.get(str(incident["id"]), 0))
        hydrated.append(hydrated_incident)
    return hydrated


def _build_correlated_recon_incidents(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Собирает зрелые цепочки поведения из нескольких сигналов по одному IP.

    Это всё ещё лёгкая корреляция, а не отдельный движок. Цель — показать оператору
    не только одиночные алерты, но и понятную progression-картину атаки.
    """
    correlation_window = 900
    recon_types = {"scanner_probe", "sensitive_path_probe", "port_scan", "ssh_user_enum"}
    correlated_types = recon_types | {"ssh_brute_force", "path_traversal", "sqli", "xss", "command_injection", "web_login_bruteforce"}
    now = int(time.time())
    by_source: dict[str, list[dict[str, object]]] = defaultdict(list)

    for event in events:
        source_ip = str(event.get("source_ip", "")).strip()
        if not source_ip:
            continue
        if str(event.get("type", "")) not in correlated_types:
            continue
        if int(event.get("timestamp", 0) or 0) < now - correlation_window:
            continue
        by_source[source_ip].append(event)

    incidents: list[dict[str, object]] = []
    for source_ip, source_events in by_source.items():
        distinct_types = sorted({str(item.get("type", "")) for item in source_events})
        source_events.sort(key=lambda item: int(item.get("timestamp", 0) or 0))
        if len(distinct_types) >= 2:
            correlated_severity = "high" if "port_scan" in distinct_types and "ssh_user_enum" in distinct_types else "medium"
            incidents.append(_make_correlated_incident(
                incident_type="recon_chain",
                source_ip=source_ip,
                severity=correlated_severity,
                confidence="high" if len(distinct_types) >= 3 else "medium",
                recommended_action="review_source_ip" if correlated_severity == "medium" else "auto_block_applied",
                summary=f"Correlated recon chain: {', '.join(distinct_types)}",
                evidence_types=distinct_types,
                events=source_events,
            ))

        if {"ssh_user_enum", "ssh_brute_force"}.issubset(distinct_types):
            incidents.append(_make_correlated_incident(
                incident_type="credential_attack_chain",
                source_ip=source_ip,
                severity="critical",
                confidence="high",
                recommended_action="auto_block_applied" if any(str(item.get("action_taken", "")) == "auto_block" for item in source_events) else "review_source_ip",
                summary="Correlated credential chain: ssh_user_enum, ssh_brute_force",
                evidence_types=[signal for signal in ("ssh_user_enum", "ssh_brute_force") if signal in distinct_types],
                events=source_events,
            ))

        web_attack_types = {"scanner_probe", "sensitive_path_probe", "path_traversal", "sqli", "xss", "command_injection", "web_login_bruteforce"}
        if len(web_attack_types.intersection(distinct_types)) >= 2 and any(signal in distinct_types for signal in {"path_traversal", "sqli", "xss", "command_injection", "web_login_bruteforce"}):
            matched_types = [signal for signal in ("scanner_probe", "sensitive_path_probe", "path_traversal", "sqli", "xss", "command_injection", "web_login_bruteforce") if signal in distinct_types]
            incidents.append(_make_correlated_incident(
                incident_type="web_attack_chain",
                source_ip=source_ip,
                severity="high",
                confidence="high" if len(matched_types) >= 3 else "medium",
                recommended_action="auto_block_applied" if any(str(item.get("action_taken", "")) == "auto_block" for item in source_events) else "review_source_ip",
                summary=f"Correlated web attack chain: {', '.join(matched_types)}",
                evidence_types=matched_types,
                events=source_events,
            ))

    return incidents


def _make_correlated_incident(
    *,
    incident_type: str,
    source_ip: str,
    severity: str,
    confidence: str,
    recommended_action: str,
    summary: str,
    evidence_types: list[str],
    events: list[dict[str, object]],
) -> dict[str, object]:
    first = events[0]
    last = events[-1]
    return {
        "id": f"{incident_type}:{source_ip}",
        "title": incident_type,
        "type": incident_type,
        "source_ip": source_ip,
        "severity": severity,
        "status": "new",
        "event_count": len(events),
        "suppressed_count": 0,
        "repeat_count": max(0, len(events) - len(evidence_types)),
        "first_seen": int(first.get("timestamp", 0) or 0),
        "last_seen": int(last.get("timestamp", 0) or 0),
        "latest_event_id": int(last.get("id", 0) or 0),
        "latest_trace_id": str(last.get("trace_id", "") or ""),
        "latest_action_taken": str(last.get("action_taken", "logged") or "logged"),
        "signal_source": "generic",
        "confidence": confidence,
        "recommended_action": recommended_action,
        "evidence_types": evidence_types,
        "summary": summary,
    }


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
        return await _load_incident_catalog(conn, event_type, limit)
    finally:
        await conn.close()


@router.get("/api/security/incidents/{incident_id}")
async def get_security_incident_detail(incident_id: str) -> dict[str, object]:
    conn = await get_db()
    try:
        return await _load_incident_detail(conn, incident_id)
    finally:
        await conn.close()


@router.get("/api/security/incidents/{incident_id}/notes")
async def get_incident_notes(
    incident_id: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> list[dict[str, object]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """
            SELECT id, incident_id, incident_type, source_ip, note, status_at_time, created_at
            FROM incident_notes
            WHERE incident_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (incident_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()


@router.post("/api/security/incidents/{incident_id}/notes")
async def add_incident_note(incident_id: str, req: IncidentNoteRequest) -> dict[str, object]:
    incident_type, source_key = _split_incident_id(incident_id)
    source_ip = "" if source_key == "host" else source_key
    now = int(time.time())
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT status FROM incident_state WHERE incident_id = ?",
            (incident_id,),
        )
        row = await cursor.fetchone()
        current_status = str(row["status"] if row else "new")
        await conn.execute(
            """
            INSERT INTO incident_notes (incident_id, incident_type, source_ip, note, status_at_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (incident_id, incident_type, source_ip, req.note, current_status, now),
        )
        await conn.commit()
    finally:
        await conn.close()
    await append_response_audit(
        trace_id=make_trace_id(),
        stage="manual_action",
        status="success",
        event_type=incident_type,
        source_ip=source_ip,
        action="incident_note",
        details={"incident_id": incident_id},
        timestamp=now,
    )
    return {
        "status": "created",
        "incident_id": incident_id,
        "note": req.note,
        "created_at": now,
    }


@router.post("/api/security/incidents/{incident_id}/status")
async def update_incident_status(incident_id: str, req: IncidentStatusRequest) -> dict[str, object]:
    incident_type, source_key = _split_incident_id(incident_id)
    source_ip = "" if source_key == "host" else source_key
    now = int(time.time())
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT OR REPLACE INTO incident_state (incident_id, status, updated_at) VALUES (?, ?, ?)",
            (incident_id, req.status, now),
        )

        if not _is_derived_incident(incident_type):
            resolved = 1 if req.status == "resolved" else 0
            if source_key == "host":
                await conn.execute(
                    "UPDATE security_events SET resolved = ? WHERE type = ? AND (source_ip = '' OR source_ip IS NULL)",
                    (resolved, incident_type),
                )
            else:
                await conn.execute(
                    "UPDATE security_events SET resolved = ? WHERE type = ? AND source_ip = ?",
                    (resolved, incident_type, source_ip),
                )
        await conn.commit()
    finally:
        await conn.close()

    await append_response_audit(
        trace_id=make_trace_id(),
        stage="manual_action",
        status="success",
        event_type=incident_type,
        source_ip=source_ip,
        action="incident_status_update",
        details={"incident_id": incident_id, "status": req.status},
        timestamp=now,
    )
    return {
        "incident_id": incident_id,
        "status": req.status,
        "updated_at": now,
    }


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
        return _deserialize_audit_rows([dict(row) for row in await cursor.fetchall()])
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
    if not is_primary_role():
        raise HTTPException(status_code=409, detail="Standby node cannot execute active response commands")
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
    if not is_primary_role():
        raise HTTPException(status_code=409, detail="Standby node cannot execute active response commands")
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
