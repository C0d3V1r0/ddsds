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
  port_scan:
    enabled: true
    window: 240
    unique_ports_threshold: 8
    action: review
  response_cooldown: 600
  medium_escalation_window: 300
  medium_escalation_threshold: 4
ml:
  log_classifier_min_confidence: 0.7
  baseline_hours: 12
  baseline_buffer_seconds: 240
  min_clean_samples: 120
  max_clean_events: 7
  host_profile: database
  maintenance_window_seconds: 600
  maintenance_commands:
    - restart_service
    - kill_process
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
    assert config.security.port_scan.enabled is True
    assert config.security.port_scan.window == 240
    assert config.security.port_scan.unique_ports_threshold == 8
    assert config.security.port_scan.action == "review"
    assert config.security.response_cooldown == 600
    assert config.security.medium_escalation_window == 300
    assert config.security.medium_escalation_threshold == 4
    assert config.ml.log_classifier_min_confidence == 0.7
    assert config.ml.baseline_hours == 12
    assert config.ml.baseline_buffer_seconds == 240
    assert config.ml.min_clean_samples == 120
    assert config.ml.max_clean_events == 7
    assert config.ml.host_profile == "database"
    assert config.ml.maintenance_window_seconds == 600
    assert config.ml.maintenance_commands == ["restart_service", "kill_process"]
    assert config.api.require_bearer_auth is True
    assert config.api.require_ws_token is True
    assert config.api.token == "bearer-token"
    assert config.api.ws_token == "ws-token"
    assert config.api.cors_origins == [
        "http://localhost:3000",
        "https://nullius.local",
    ]
