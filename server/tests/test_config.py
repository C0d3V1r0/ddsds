import pytest
from config import load_config, NulliusConfig

def test_load_config_from_yaml(tmp_path):
    yaml_content = """
agent:
  metrics_interval: 5
  services_interval: 30
  log_sources:
    - /var/log/auth.log

security:
  ssh_brute_force:
    threshold: 5
    window: 300
    action: block
    block_duration: 86400
  web_attacks:
    enabled: true
    action: block
  auto_block: true
  allowed_services:
    - nginx
    - postgresql

ml:
  anomaly_detection: true
  training_period: 86400
  sensitivity: medium
"""
    config_file = tmp_path / "nullius.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert config.agent.metrics_interval == 5
    assert config.security.ssh_brute_force.threshold == 5
    assert config.security.allowed_services == ["nginx", "postgresql"]
    assert config.ml.sensitivity == "medium"

def test_load_config_defaults(tmp_path):
    yaml_content = "agent:\n  metrics_interval: 10\n"
    config_file = tmp_path / "nullius.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert config.agent.metrics_interval == 10
    assert config.agent.services_interval == 30  # default
    assert config.security.auto_block is True  # default
