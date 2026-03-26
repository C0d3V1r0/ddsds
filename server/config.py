# Загрузка конфигурации из YAML-файла с валидацией через pydantic
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel


class AgentConfig(BaseModel):
    metrics_interval: int = 5
    services_interval: int = 30
    log_sources: list[str] = ["/var/log/auth.log"]


class SSHBruteForceConfig(BaseModel):
    threshold: int = 5
    window: int = 300
    action: str = "block"
    block_duration: int = 86400


class WebAttacksConfig(BaseModel):
    enabled: bool = True
    action: str = "block"


class SecurityConfig(BaseModel):
    ssh_brute_force: SSHBruteForceConfig = SSHBruteForceConfig()
    web_attacks: WebAttacksConfig = WebAttacksConfig()
    auto_block: bool = True
    allowed_services: list[str] = ["nginx", "postgresql", "redis", "mysql", "docker"]


class MLConfig(BaseModel):
    anomaly_detection: bool = True
    training_period: int = 86400
    sensitivity: str = "medium"


class APIConfig(BaseModel):
    require_bearer_auth: bool = False
    require_ws_token: bool = False


class NulliusConfig(BaseModel):
    agent: AgentConfig = AgentConfig()
    security: SecurityConfig = SecurityConfig()
    ml: MLConfig = MLConfig()
    api: APIConfig = APIConfig()


def load_config(path: str) -> NulliusConfig:
    """Загружает конфигурацию из YAML-файла. Если файл не найден — возвращает дефолты."""
    config_path = Path(path)
    if not config_path.exists():
        return NulliusConfig()
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return NulliusConfig(**data)
