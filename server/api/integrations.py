# REST API для внешних интеграций: Telegram и Slack.
from fastapi import APIRouter
from pydantic import BaseModel, Field

from integrations.telegram import (
    configure_telegram_bot,
    get_telegram_settings,
    send_telegram_test_message,
)
from integrations.slack import (
    configure_slack_webhook,
    get_slack_settings,
    send_slack_test_message,
)

router = APIRouter(prefix="/api/integrations")


class TelegramConfigRequest(BaseModel):
    token: str = Field(default="", max_length=256)
    notify_auto_block: bool = True
    notify_high_severity: bool = False
    notify_min_severity: str = Field(default="high", max_length=16)
    quiet_hours_start: str = Field(default="", max_length=5)
    quiet_hours_end: str = Field(default="", max_length=5)


class SlackConfigRequest(BaseModel):
    webhook_url: str = Field(default="", max_length=1024)
    notify_auto_block: bool = True
    notify_high_severity: bool = False
    notify_min_severity: str = Field(default="high", max_length=16)
    quiet_hours_start: str = Field(default="", max_length=5)
    quiet_hours_end: str = Field(default="", max_length=5)


@router.get("/telegram")
async def get_telegram_config() -> dict[str, object]:
    return await get_telegram_settings()


@router.post("/telegram")
async def save_telegram_config(payload: TelegramConfigRequest) -> dict[str, object]:
    return await configure_telegram_bot(
        token=payload.token,
        notify_auto_block=payload.notify_auto_block,
        notify_high_severity=payload.notify_high_severity,
        notify_min_severity=payload.notify_min_severity,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
    )


@router.post("/telegram/test")
async def telegram_test_message() -> dict[str, object]:
    return await send_telegram_test_message()


@router.get("/slack")
async def get_slack_config() -> dict[str, object]:
    return await get_slack_settings()


@router.post("/slack")
async def save_slack_config(payload: SlackConfigRequest) -> dict[str, object]:
    return await configure_slack_webhook(
        webhook_url=payload.webhook_url,
        notify_auto_block=payload.notify_auto_block,
        notify_high_severity=payload.notify_high_severity,
        notify_min_severity=payload.notify_min_severity,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
    )


@router.post("/slack/test")
async def slack_test_message() -> dict[str, object]:
    return await send_slack_test_message()
