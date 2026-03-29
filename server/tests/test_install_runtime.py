from starlette.testclient import TestClient
import pytest
import fcntl


def test_create_app_reads_agent_key_next_to_config(tmp_path, monkeypatch):
    from main import create_app

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "nullius.yaml"
    key_path = config_dir / "agent.key"
    lock_path = config_dir / "primary.lock"
    db_path = tmp_path / "test.db"

    config_path.write_text(
        f"""
deployment:
  role: primary
  node_name: test-primary
  primary_lock_path: {lock_path}
agent:
  metrics_interval: 5
  services_interval: 30
  processes_interval: 10
  log_sources: []
security:
  auto_block: true
ml:
  anomaly_detection: false
api:
  require_bearer_auth: false
  require_ws_token: false
"""
    )
    key_path.write_text("adjacent-secret")
    monkeypatch.delenv("NULLIUS_AGENT_SECRET", raising=False)

    app = create_app(
        config_path=str(config_path),
        db_path=str(db_path),
    )

    client = TestClient(app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "adjacent-secret"})
        resp = ws.receive_json()
        assert resp["type"] == "auth_ok"


def test_create_app_rejects_bearer_auth_without_dedicated_token(tmp_path, monkeypatch):
    from main import create_app

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "nullius.yaml"
    key_path = config_dir / "agent.key"
    lock_path = config_dir / "primary.lock"
    db_path = tmp_path / "test.db"

    config_path.write_text(
        f"""
deployment:
  role: primary
  node_name: test-primary
  primary_lock_path: {lock_path}
agent:
  metrics_interval: 5
  services_interval: 30
  processes_interval: 10
  log_sources: []
security:
  auto_block: true
ml:
  anomaly_detection: false
api:
  require_bearer_auth: true
  require_ws_token: false
  token: ""
"""
    )
    key_path.write_text("adjacent-secret")
    monkeypatch.delenv("NULLIUS_AGENT_SECRET", raising=False)
    monkeypatch.delenv("NULLIUS_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="Bearer auth включён"):
        create_app(
            config_path=str(config_path),
            db_path=str(db_path),
        )


def test_create_app_rejects_ws_auth_without_ui_token(tmp_path, monkeypatch):
    from main import create_app

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "nullius.yaml"
    key_path = config_dir / "agent.key"
    lock_path = config_dir / "primary.lock"
    db_path = tmp_path / "test.db"

    config_path.write_text(
        f"""
deployment:
  role: primary
  node_name: test-primary
  primary_lock_path: {lock_path}
agent:
  metrics_interval: 5
  services_interval: 30
  processes_interval: 10
  log_sources: []
security:
  auto_block: true
ml:
  anomaly_detection: false
api:
  require_bearer_auth: false
  require_ws_token: true
  ws_token: ""
"""
    )
    key_path.write_text("adjacent-secret")
    monkeypatch.delenv("NULLIUS_AGENT_SECRET", raising=False)
    monkeypatch.delenv("NULLIUS_WS_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="WS auth включён"):
        create_app(
            config_path=str(config_path),
            db_path=str(db_path),
        )


def test_create_app_exposes_standby_deployment_status(tmp_path, monkeypatch):
    from main import create_app

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "nullius.yaml"
    key_path = config_dir / "agent.key"
    lock_path = config_dir / "primary.lock"
    db_path = tmp_path / "test.db"

    config_path.write_text(
        f"""
deployment:
  role: standby
  node_name: standby-a
  primary_lock_path: {lock_path}
agent:
  metrics_interval: 5
  services_interval: 30
  processes_interval: 10
  log_sources: []
security:
  auto_block: true
ml:
  anomaly_detection: false
api:
  require_bearer_auth: false
  require_ws_token: false
"""
    )
    key_path.write_text("adjacent-secret")
    monkeypatch.delenv("NULLIUS_AGENT_SECRET", raising=False)

    app = create_app(
        config_path=str(config_path),
        db_path=str(db_path),
    )
    client = TestClient(app)
    response = client.get("/api/deployment")

    assert response.status_code == 200
    assert response.json()["role"] == "standby"
    assert response.json()["background_tasks_enabled"] is False
    assert response.json()["active_response_enabled"] is False
    assert response.json()["failover"]["enabled"] is False


def test_create_app_refuses_second_primary_when_lock_is_held(tmp_path, monkeypatch):
    from main import create_app

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "nullius.yaml"
    key_path = config_dir / "agent.key"
    db_path = tmp_path / "test.db"
    lock_path = tmp_path / "primary.lock"

    config_path.write_text(
        f"""
deployment:
  role: primary
  node_name: primary-a
  primary_lock_path: {lock_path}
agent:
  metrics_interval: 5
  services_interval: 30
  processes_interval: 10
  log_sources: []
security:
  auto_block: true
ml:
  anomaly_detection: false
api:
  require_bearer_auth: false
  require_ws_token: false
"""
    )
    key_path.write_text("adjacent-secret")
    monkeypatch.delenv("NULLIUS_AGENT_SECRET", raising=False)

    with open(lock_path, "a+", encoding="utf-8") as fd:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="Primary lock already held"):
            create_app(
                config_path=str(config_path),
                db_path=str(db_path),
            )
