from starlette.testclient import TestClient
import pytest


def test_create_app_reads_agent_key_next_to_config(tmp_path, monkeypatch):
    from main import create_app

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "nullius.yaml"
    key_path = config_dir / "agent.key"
    db_path = tmp_path / "test.db"

    config_path.write_text(
        """
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
    db_path = tmp_path / "test.db"

    config_path.write_text(
        """
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
    db_path = tmp_path / "test.db"

    config_path.write_text(
        """
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
