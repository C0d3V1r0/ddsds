# Self-protection API: встроенная проверка безопасности самой платформы
import os
import stat
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Request

router = APIRouter()


def _is_local_origin(origin: str) -> bool:
    value = str(origin or "").strip().lower()
    if not value:
        return False
    if value in {"http://localhost:3000", "http://127.0.0.1:3000", "http://localhost", "http://127.0.0.1"}:
        return True
    parsed = urlparse(value)
    return parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def _has_broad_file_permissions(path: Path) -> bool:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        return False
    return bool(mode & 0o077)


def _check(
    code: str,
    status: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "code": code,
        "status": status,
        "severity": severity,
        "title": title,
        "description": description,
        "recommendation": recommendation,
    }


def evaluate_self_protection(config, *, config_path: str, agent_secret_present: bool) -> dict[str, object]:
    """Оценивает, насколько сама инсталляция Nullius защищена от misconfiguration."""
    checks: list[dict[str, str]] = []
    config_file = Path(config_path)
    agent_key_path = config_file.with_name("agent.key")

    public_ui_surface = any(not _is_local_origin(origin) for origin in config.api.cors_origins)
    cors_is_open = any(str(origin).strip() == "*" for origin in config.api.cors_origins)
    agent_url = urlparse(str(config.agent.server_url or "").strip())
    agent_host = (agent_url.hostname or "").strip().lower()
    remote_agent_transport = agent_url.scheme == "ws" and agent_host not in {"localhost", "127.0.0.1", "::1", ""}

    if not agent_secret_present:
        checks.append(_check(
            "agent_secret_missing",
            "failing",
            "critical",
            "Нет постоянного секрета агента",
            "Агентский канал может работать на временном секрете, что недопустимо для production.",
            "Задай `NULLIUS_AGENT_SECRET` или положи `agent.key` рядом с `nullius.yaml`.",
        ))
    else:
        checks.append(_check(
            "agent_secret_present",
            "healthy",
            "low",
            "Постоянный секрет агента задан",
            "Агентский WebSocket канал использует постоянный доверенный секрет.",
            "Оставь secret выделенным и не переиспользуй его в UI-слое.",
        ))

    if _has_broad_file_permissions(config_file):
        checks.append(_check(
            "config_permissions_open",
            "warning",
            "high",
            "Конфиг доступен слишком широко",
            "Файл `nullius.yaml` имеет group/world-доступ и может раскрыть чувствительные настройки.",
            "Поставь `chmod 600` на `nullius.yaml` и владельца `nullius:nullius`.",
        ))

    if agent_key_path.exists() and _has_broad_file_permissions(agent_key_path):
        checks.append(_check(
            "agent_key_permissions_open",
            "warning",
            "critical",
            "agent.key доступен слишком широко",
            "Секрет агента не должен быть доступен группе или всем пользователям хоста.",
            "Поставь `chmod 600` на `agent.key` и проверь владельца файла.",
        ))

    if cors_is_open:
        checks.append(_check(
            "cors_wildcard",
            "failing",
            "critical",
            "CORS открыт через wildcard",
            "Любой origin может обращаться к API браузером, что резко увеличивает attack surface.",
            "Замени `*` на явный список доверенных origin.",
        ))
    else:
        checks.append(_check(
            "cors_scoped",
            "healthy",
            "low",
            "CORS ограничен доверенными origin",
            "Список браузерных origin не открыт через wildcard.",
            "Держи список `api.cors_origins` минимальным.",
        ))

    if public_ui_surface and not config.api.require_bearer_auth:
        checks.append(_check(
            "bearer_auth_disabled_public_ui",
            "warning",
            "high",
            "Bearer auth выключен при внешнем UI",
            "Если UI доступен не только с localhost, дополнительный API-токен заметно повышает стойкость продукта.",
            "Включи `api.require_bearer_auth` и задай отдельный `api.token`.",
        ))

    if public_ui_surface and not config.api.require_ws_token:
        checks.append(_check(
            "ws_auth_disabled_public_ui",
            "warning",
            "medium",
            "WS auth выключен при внешнем UI",
            "Live WebSocket остаётся без отдельного UI-токена, что ухудшает разделение доверия.",
            "Включи `api.require_ws_token` и задай `api.ws_token` или используй UI API token.",
        ))

    if config.api.require_bearer_auth and config.api.require_ws_token and config.api.token and config.api.ws_token and config.api.token == config.api.ws_token:
        checks.append(_check(
            "shared_ui_tokens",
            "warning",
            "medium",
            "UI API и WS используют один и тот же токен",
            "Это допустимо, но уменьшает разделение секретов между HTTP и live-каналом.",
            "Для более жёсткой модели задай отдельный `api.ws_token`.",
        ))

    if remote_agent_transport:
        checks.append(_check(
            "remote_agent_plain_ws",
            "warning",
            "high",
            "Удалённый агент подключается по plain WS",
            "Нешифрованный агентский transport опасен для внешних сетей и межхостового трафика.",
            "Используй `wss://` для удалённого агента или держи агент только на loopback/в доверенной сети.",
        ))

    if config.agent.tls_skip_verify:
        checks.append(_check(
            "agent_tls_skip_verify",
            "failing",
            "critical",
            "У агента отключена проверка TLS",
            "Такой режим упрощает MITM и годится только для аварийной диагностики.",
            "Верни `agent.tls_skip_verify: false` и настрой валидный сертификат.",
        ))

    if str(config.deployment.role).strip().lower() == "standby" and bool(config.failover.enabled) and not str(config.failover.primary_api_url).strip():
        checks.append(_check(
            "standby_failover_target_missing",
            "warning",
            "medium",
            "Для standby включён failover без primary API URL",
            "Оркестратор failover не сможет безопасно оценивать доступность primary-узла без явного адреса его health API.",
            "Задай `failover.primary_api_url`, например `http://10.0.0.10:8000`.",
        ))

    healthy_count = sum(1 for check in checks if check["status"] == "healthy")
    warning_count = sum(1 for check in checks if check["status"] == "warning")
    failing_count = sum(1 for check in checks if check["status"] == "failing")

    if failing_count:
        level = "critical"
    elif any(check["severity"] == "high" for check in checks if check["status"] == "warning"):
        level = "high"
    elif warning_count:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "healthy_count": healthy_count,
        "warning_count": warning_count,
        "failing_count": failing_count,
        "checks": checks,
    }


@router.get("/api/self-protection")
async def get_self_protection_status(request: Request) -> dict[str, object]:
    config = request.app.state.config
    config_path = str(getattr(request.app.state, "config_path", "nullius.yaml"))
    agent_secret_present = bool(os.environ.get("NULLIUS_AGENT_SECRET", "").strip())
    if not agent_secret_present:
        agent_secret_present = Path(config_path).with_name("agent.key").exists()
    status = evaluate_self_protection(config, config_path=config_path, agent_secret_present=agent_secret_present)
    deployment_state = getattr(request.app.state, "deployment", {}) or {}
    if deployment_state.get("role") == "primary":
        if not deployment_state.get("primary_lock_held"):
            status["checks"].append(_check(
                "primary_lock_missing",
                "failing",
                "critical",
                "Primary-узел не удерживает защитный lock",
                "Без primary lock повышается риск split-brain или параллельного запуска второго активного узла.",
                "Проверь `deployment.primary_lock_path` и перезапусти сервис после исправления доступа к lock-файлу.",
            ))
        else:
            status["checks"].append(_check(
                "primary_lock_held",
                "healthy",
                "low",
                "Primary lock удерживается корректно",
                "Активный узел удерживает эксклюзивный lock и снижает риск split-brain при warm standby.",
                "Оставь `deployment.primary_lock_path` на общем контролируемом storage, если разворачиваешь standby-пару.",
            ))
    status["healthy_count"] = sum(1 for check in status["checks"] if check["status"] == "healthy")
    status["warning_count"] = sum(1 for check in status["checks"] if check["status"] == "warning")
    status["failing_count"] = sum(1 for check in status["checks"] if check["status"] == "failing")
    if status["failing_count"]:
        status["level"] = "critical"
    elif any(check["severity"] == "high" for check in status["checks"] if check["status"] == "warning"):
        status["level"] = "high"
    elif status["warning_count"]:
        status["level"] = "medium"
    else:
        status["level"] = "low"
    return status
