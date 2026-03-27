# Загрузка конфигурации из YAML-файла с валидацией через pydantic
from pathlib import Path
import yaml
from pydantic import BaseModel, Field


# Настройки агента: интервалы сбора данных, адрес сервера, источники логов
class AgentConfig(BaseModel):
    metrics_interval: int = 5
    services_interval: int = 30
    processes_interval: int = 10
    server_url: str = "ws://127.0.0.1:8000/ws/agent"
    tls_skip_verify: bool = False
    log_sources: list[str] = Field(default_factory=lambda: ["/var/log/auth.log"])


# Пороги и параметры детекции SSH brute force
class SSHBruteForceConfig(BaseModel):
    threshold: int = 5
    window: int = 300
    action: str = "block"
    block_duration: int = 86400


# Настройки детекции веб-атак (SQLi, XSS и т.д.)
class WebAttacksConfig(BaseModel):
    enabled: bool = True
    action: str = "block"


# Политики безопасности: автоблокировка, разрешённые сервисы
class SecurityConfig(BaseModel):
    ssh_brute_force: SSHBruteForceConfig = Field(default_factory=SSHBruteForceConfig)
    web_attacks: WebAttacksConfig = Field(default_factory=WebAttacksConfig)
    auto_block: bool = True
    allowed_services: list[str] = Field(
        default_factory=lambda: ["nginx", "postgresql", "redis", "mysql", "docker"]
    )


# Параметры ML-моделей: anomaly detection, чувствительность
class MLConfig(BaseModel):
    anomaly_detection: bool = True
    training_period: int = 86400
    sensitivity: str = "medium"


# Настройки REST API: аутентификация, CORS
class APIConfig(BaseModel):
    require_bearer_auth: bool = False
    require_ws_token: bool = False
    token: str = ""
    ws_token: str = ""
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


# Корневой конфиг приложения, объединяет все секции
class NulliusConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    api: APIConfig = Field(default_factory=APIConfig)


def load_config(path: str) -> NulliusConfig:
    """Загружает конфигурацию из YAML-файла. Если файл не найден — возвращает дефолты."""
    config_path = Path(path)
    if not config_path.exists():
        return NulliusConfig()
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return NulliusConfig(**data)
