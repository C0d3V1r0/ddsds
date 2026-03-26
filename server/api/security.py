# REST API для событий безопасности и управления блокировкой IP
import ipaddress
import time
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator
from db import get_db, enqueue_write

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
        return [dict(row) for row in rows]
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
    # Запись через очередь — не блокируем БД конкурентными записями
    await enqueue_write(
        "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, 0)",
        (req.ip, req.reason, now, expires),
    )
    return {"status": "blocked", "ip": req.ip}


@router.post("/api/security/unblock")
async def unblock_ip(req: UnblockRequest) -> dict[str, str]:
    await enqueue_write("DELETE FROM blocked_ips WHERE ip = ?", (req.ip,))
    return {"status": "unblocked", "ip": req.ip}
