from config import load_config


def test_load_config_preserves_full_agent_schema(tmp_path):
    config_path = tmp_path / "nullius.yaml"
    config_path.write_text(
        """
agent:
  metrics_interval: 9
  services_interval: 21
  processes_interval: 13
  server_url: ws://10.0.0.5:8000/ws/agent
  tls_skip_verify: true
  log_sources:
    - /var/log/auth.log
    - /var/log/nginx/access.log
security:
  auto_block: false
api:
  require_bearer_auth: true
  require_ws_token: true
  token: bearer-token
  ws_token: ws-token
  cors_origins:
    - http://localhost:3000
    - https://nullius.local
"""
    )

    config = load_config(str(config_path))

    assert config.agent.metrics_interval == 9
    assert config.agent.services_interval == 21
    assert config.agent.processes_interval == 13
    assert config.agent.server_url == "ws://10.0.0.5:8000/ws/agent"
    assert config.agent.tls_skip_verify is True
    assert config.agent.log_sources == [
        "/var/log/auth.log",
        "/var/log/nginx/access.log",
    ]
    assert config.security.auto_block is False
    assert config.api.require_bearer_auth is True
    assert config.api.require_ws_token is True
    assert config.api.token == "bearer-token"
    assert config.api.ws_token == "ws-token"
    assert config.api.cors_origins == [
        "http://localhost:3000",
        "https://nullius.local",
    ]
