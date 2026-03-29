# Статус роли развёртывания: primary или standby.
from fastapi import APIRouter, Request

from deployment import get_deployment_state

router = APIRouter()


@router.get("/api/deployment")
async def get_deployment_status(request: Request) -> dict[str, object]:
    """Возвращает роль текущего узла и включённые runtime-возможности."""
    state = get_deployment_state()
    config = request.app.state.config
    state["failover"] = {
        "enabled": bool(config.failover.enabled),
        "primary_api_url": str(config.failover.primary_api_url or ""),
        "check_interval": int(config.failover.check_interval),
        "failure_threshold": int(config.failover.failure_threshold),
        "cooloff_seconds": int(config.failover.cooloff_seconds),
    }
    return state
