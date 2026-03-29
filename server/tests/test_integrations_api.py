import pytest
import time
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_telegram_settings_defaults(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/integrations/telegram")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["chat_bound"] is False
    assert data["notify_high_severity"] is False


@pytest.mark.asyncio
async def test_save_telegram_settings_persists_bot_info(test_app, monkeypatch):
    async def fake_telegram_api(token: str, method: str, params=None):
        assert token == "123:token"
        assert method == "getMe"
        return {
            "ok": True,
            "result": {
                "username": "nullius_test_bot",
                "first_name": "Nullius Bot",
            },
        }

    monkeypatch.setattr("integrations.telegram._telegram_api", fake_telegram_api)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/integrations/telegram", json={
            "token": "123:token",
            "notify_auto_block": True,
            "notify_high_severity": True,
            "notify_min_severity": "critical",
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "07:00",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["bot_username"] == "nullius_test_bot"
    assert data["chat_bound"] is False
    assert data["notify_high_severity"] is True
    assert data["notify_min_severity"] == "critical"
    assert data["quiet_hours_start"] == "23:00"
    assert data["quiet_hours_end"] == "07:00"


@pytest.mark.asyncio
async def test_telegram_poll_cycle_binds_chat_on_start(test_app, monkeypatch):
    from integrations.telegram import configure_telegram_bot, get_telegram_settings, run_telegram_poll_cycle

    calls: list[tuple[str, str]] = []

    async def fake_telegram_api(token: str, method: str, params=None):
        calls.append((token, method))
        if method == "getMe":
            return {
                "ok": True,
                "result": {
                    "username": "nullius_test_bot",
                    "first_name": "Nullius Bot",
                },
            }
        if method == "getUpdates":
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "text": "/start",
                            "chat": {
                                "id": 777,
                                "username": "operator",
                                "first_name": "Ops",
                            },
                        },
                    },
                ],
            }
        if method == "sendMessage":
            return {"ok": True, "result": {"message_id": 1}}
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr("integrations.telegram._telegram_api", fake_telegram_api)

    await configure_telegram_bot(
        token="123:token",
        notify_auto_block=True,
        notify_high_severity=False,
        notify_min_severity="high",
        quiet_hours_start="",
        quiet_hours_end="",
    )
    await run_telegram_poll_cycle()
    settings = await get_telegram_settings()

    assert settings["chat_bound"] is True
    assert settings["chat_title"] == "@operator"
    assert ("123:token", "sendMessage") in calls


@pytest.mark.asyncio
async def test_telegram_test_endpoint_sends_message_when_chat_is_bound(test_app, monkeypatch):
    from integrations.telegram import configure_telegram_bot, run_telegram_poll_cycle

    async def fake_telegram_api(token: str, method: str, params=None):
        if method == "getMe":
            return {"ok": True, "result": {"username": "nullius_test_bot", "first_name": "Nullius Bot"}}
        if method == "getUpdates":
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {"text": "/start", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                ],
            }
        if method == "sendMessage":
            return {"ok": True, "result": {"message_id": 42}}
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr("integrations.telegram._telegram_api", fake_telegram_api)

    await configure_telegram_bot(
        token="123:token",
        notify_auto_block=True,
        notify_high_severity=False,
        notify_min_severity="high",
        quiet_hours_start="",
        quiet_hours_end="",
    )
    await run_telegram_poll_cycle()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/integrations/telegram/test")

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_telegram_poll_cycle_handles_mode_and_blocked_commands(test_app, monkeypatch):
    from integrations.telegram import configure_telegram_bot, run_telegram_poll_cycle
    from security.mode import set_operation_mode
    from db import get_db

    sent_texts: list[str] = []

    async def fake_telegram_api(token: str, method: str, params=None):
        if method == "getMe":
            return {"ok": True, "result": {"username": "nullius_test_bot", "first_name": "Nullius Bot"}}
        if method == "getUpdates":
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {"text": "/start", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                    {
                        "update_id": 2,
                        "message": {"text": "/mode", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                    {
                        "update_id": 3,
                        "message": {"text": "/blocked", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                ],
            }
        if method == "sendMessage":
            sent_texts.append(str((params or {}).get("text", "")))
            return {"ok": True, "result": {"message_id": 42}}
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr("integrations.telegram._telegram_api", fake_telegram_api)

    conn = await get_db()
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) VALUES (?, ?, ?, ?)",
        ("10.0.0.5", "manual", 1, 0),
    )
    await conn.commit()
    await conn.close()

    await configure_telegram_bot(
        token="123:token",
        notify_auto_block=True,
        notify_high_severity=False,
        notify_min_severity="high",
        quiet_hours_start="",
        quiet_hours_end="",
    )
    await set_operation_mode("assist")
    await run_telegram_poll_cycle()

    assert any("Current mode: assist" in text for text in sent_texts)
    assert any("10.0.0.5" in text for text in sent_texts)


@pytest.mark.asyncio
async def test_get_slack_settings_defaults(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/integrations/slack")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["notify_high_severity"] is False


@pytest.mark.asyncio
async def test_save_slack_settings_persists_webhook(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/integrations/slack", json={
            "webhook_url": "https://hooks.slack.com/services/T000/B000/XXXX",
            "notify_auto_block": True,
            "notify_high_severity": True,
            "notify_min_severity": "medium",
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "06:00",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["notify_auto_block"] is True
    assert data["notify_high_severity"] is True
    assert data["notify_min_severity"] == "medium"
    assert data["quiet_hours_start"] == "22:00"
    assert data["quiet_hours_end"] == "06:00"


@pytest.mark.asyncio
async def test_slack_test_endpoint_sends_message(test_app, monkeypatch):
    from integrations.slack import configure_slack_webhook

    async def fake_send_payload(webhook_url: str, payload: dict[str, object]) -> None:
        assert webhook_url == "https://hooks.slack.com/services/T000/B000/XXXX"
        assert "Nullius" in str(payload.get("text", ""))

    monkeypatch.setattr("integrations.slack._send_payload", fake_send_payload)
    await configure_slack_webhook(
        webhook_url="https://hooks.slack.com/services/T000/B000/XXXX",
        notify_auto_block=True,
        notify_high_severity=False,
        notify_min_severity="high",
        quiet_hours_start="",
        quiet_hours_end="",
    )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/integrations/slack/test")

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


def test_should_emit_notification_suppresses_duplicates():
    from integrations.service import should_emit_notification

    event = {"type": "ssh_brute_force", "source_ip": "10.0.0.5", "action_taken": "auto_block"}
    assert should_emit_notification(event, now=1000) is True
    assert should_emit_notification(event, now=1100) is False
    assert should_emit_notification(event, now=1405) is True


@pytest.mark.asyncio
async def test_telegram_poll_cycle_handles_block_and_unblock_commands(test_app, monkeypatch):
    from db import get_db
    from integrations.telegram import configure_telegram_bot, run_telegram_poll_cycle

    sent_texts: list[str] = []

    async def fake_telegram_api(token: str, method: str, params=None):
        if method == "getMe":
            return {"ok": True, "result": {"username": "nullius_test_bot", "first_name": "Nullius Bot"}}
        if method == "getUpdates":
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {"text": "/start", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                    {
                        "update_id": 2,
                        "message": {"text": "/block 10.0.0.8 ssh_recon", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                    {
                        "update_id": 3,
                        "message": {"text": "/unblock 10.0.0.8", "chat": {"id": 777, "first_name": "Ops"}},
                    },
                ],
            }
        if method == "sendMessage":
            sent_texts.append(str((params or {}).get("text", "")))
            return {"ok": True, "result": {"message_id": 42}}
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr("integrations.telegram._telegram_api", fake_telegram_api)

    await configure_telegram_bot(
        token="123:token",
        notify_auto_block=True,
        notify_high_severity=False,
        notify_min_severity="high",
        quiet_hours_start="",
        quiet_hours_end="",
    )
    await run_telegram_poll_cycle()

    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT ip FROM blocked_ips WHERE ip = ?", ("10.0.0.8",))
        row = await cursor.fetchone()
    finally:
        await conn.close()

    assert row is None
    assert any("Blocked: 10.0.0.8" in text for text in sent_texts)
    assert any("Unblocked: 10.0.0.8" in text for text in sent_texts)


@pytest.mark.asyncio
async def test_slack_payload_contains_recommendation_and_trace(monkeypatch):
    from integrations.slack import _build_event_payload

    payload = _build_event_payload({
        "type": "ssh_brute_force",
        "source_ip": "10.0.0.7",
        "severity": "critical",
        "action_taken": "auto_block",
        "description": "Rule+ML confirmed: ssh_brute_force",
        "recommended_action": "auto_block_applied",
        "trace_id": "trace-123",
    })

    assert payload["text"] == "Nullius: автоблокировка"
    rendered = str(payload["blocks"])
    assert "auto_block_applied" in rendered
    assert "trace-123" in rendered


def test_notification_policy_respects_threshold_and_quiet_hours():
    from integrations.policy import should_notify_by_policy

    settings = {
        "notify_auto_block": True,
        "notify_high_severity": True,
        "notify_min_severity": "critical",
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "07:00",
    }

    assert should_notify_by_policy(settings, {"action_taken": "auto_block", "severity": "medium"}) is True
    assert should_notify_by_policy(settings, {"action_taken": "logged", "severity": "high"}) is False


def test_notification_policy_suppresses_routine_events_in_quiet_hours(monkeypatch):
    from integrations import policy

    monkeypatch.setattr(policy.time, "localtime", lambda _: time.struct_time((2026, 3, 29, 1, 0, 0, 6, 88, -1)))
    settings = {
        "notify_auto_block": True,
        "notify_high_severity": True,
        "notify_min_severity": "medium",
        "quiet_hours_start": "00:00",
        "quiet_hours_end": "02:00",
    }

    assert policy.should_notify_by_policy(settings, {"action_taken": "logged", "severity": "critical"}, now=3600) is False
