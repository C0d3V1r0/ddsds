import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path

# Добавляем server/ в sys.path для корректного импорта модулей
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_config_path(tmp_path):
    config = """
agent:
  metrics_interval: 5
  services_interval: 30
  log_sources: []
security:
  ssh_brute_force:
    threshold: 3
    window: 60
    action: block
    block_duration: 3600
  web_attacks:
    enabled: true
    action: block
  port_scan:
    enabled: true
    window: 120
    unique_ports_threshold: 4
    action: review
  auto_block: true
  allowed_services:
    - nginx
    - test-service
ml:
  anomaly_detection: false
  training_period: 86400
  sensitivity: medium
api:
  require_bearer_auth: false
  require_ws_token: false
"""
    p = tmp_path / "nullius.yaml"
    p.write_text(config)
    return str(p)


@pytest.fixture
def secure_test_config_path(tmp_path):
    config = """
agent:
  metrics_interval: 5
  services_interval: 30
  log_sources: []
security:
  ssh_brute_force:
    threshold: 3
    window: 60
    action: block
    block_duration: 3600
  web_attacks:
    enabled: true
    action: block
  port_scan:
    enabled: true
    window: 120
    unique_ports_threshold: 4
    action: review
  auto_block: true
  allowed_services:
    - nginx
ml:
  anomaly_detection: false
  training_period: 86400
  sensitivity: medium
api:
  require_bearer_auth: true
  require_ws_token: true
  token: test-api-token-for-tests
  ws_token: test-ws-token-for-tests
"""
    p = tmp_path / "secure-nullius.yaml"
    p.write_text(config)
    return str(p)


TEST_AGENT_SECRET = "test-secret-for-tests"
TEST_API_TOKEN = "test-api-token-for-tests"
TEST_WS_TOKEN = "test-ws-token-for-tests"


@pytest_asyncio.fixture
async def test_app(tmp_path, test_config_path, monkeypatch):
    from main import create_app
    from db import init_db
    from api.auth import set_api_token
    # Задаём секрет агента через env для предсказуемости тестов
    monkeypatch.setenv("NULLIUS_AGENT_SECRET", TEST_AGENT_SECRET)
    db_path = str(tmp_path / "test.db")
    # Явно инициализируем БД, т.к. lifespan не запускается в тестовом транспорте
    await init_db(db_path)
    app = create_app(
        config_path=test_config_path,
        db_path=db_path
    )
    # Отключаем API-аутентификацию для тестов (пустой токен пропускает проверку)
    set_api_token("")
    yield app


@pytest_asyncio.fixture
async def secure_test_app(tmp_path, secure_test_config_path, monkeypatch):
    from main import create_app
    from db import init_db

    monkeypatch.setenv("NULLIUS_AGENT_SECRET", TEST_AGENT_SECRET)
    db_path = str(tmp_path / "secure-test.db")
    await init_db(db_path)
    app = create_app(
        config_path=secure_test_config_path,
        db_path=db_path
    )
    yield app
