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
    log_sources: list[str] = Field(
        default_factory=lambda: [
            "/var/log/auth.log",
            "/var/log/nginx/access.log",
            "/var/log/nginx/error.log",
            "/var/log/ufw.log",
            "/var/log/kern.log",
        ]
    )


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


class PortScanConfig(BaseModel):
    enabled: bool = True
    window: int = 120
    unique_ports_threshold: int = 12
    action: str = "review"


# Политики безопасности: автоблокировка, разрешённые сервисы
class SecurityConfig(BaseModel):
    ssh_brute_force: SSHBruteForceConfig = Field(default_factory=SSHBruteForceConfig)
    web_attacks: WebAttacksConfig = Field(default_factory=WebAttacksConfig)
    port_scan: PortScanConfig = Field(default_factory=PortScanConfig)
    auto_block: bool = True
    response_cooldown: int = 900
    medium_escalation_window: int = 900
    medium_escalation_threshold: int = 3
    allowed_services: list[str] = Field(
        default_factory=lambda: ["nginx", "postgresql", "redis", "mysql", "docker"]
    )


# Параметры ML-моделей: anomaly detection, чувствительность
class MLConfig(BaseModel):
    anomaly_detection: bool = True
    training_period: int = 86400
    sensitivity: str = "medium"
    log_classifier_min_confidence: float = 0.6
    baseline_hours: int = 24
    baseline_buffer_seconds: int = 300
    min_clean_samples: int = 100
    max_clean_events: int = 10
    host_profile: str = "generic"
    maintenance_window_seconds: int = 900
    maintenance_commands: list[str] = Field(
        default_factory=lambda: ["restart_service", "kill_process", "force_kill_process"]
    )


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
