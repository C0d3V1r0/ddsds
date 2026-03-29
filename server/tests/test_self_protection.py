from api.self_protection import evaluate_self_protection
from config import NulliusConfig


def test_self_protection_warns_about_public_ui_without_api_auth(tmp_path):
    config = NulliusConfig()
    config.api.cors_origins = ["https://nullius.example.com"]
    config.api.require_bearer_auth = False
    config.api.require_ws_token = False

    config_path = tmp_path / "nullius.yaml"
    config_path.write_text("api: {}\n")
    (tmp_path / "agent.key").write_text("secret")

    result = evaluate_self_protection(config, config_path=str(config_path), agent_secret_present=True)
    codes = {item["code"]: item for item in result["checks"]}

    assert result["level"] in {"high", "critical"}
    assert codes["bearer_auth_disabled_public_ui"]["status"] == "warning"
    assert codes["ws_auth_disabled_public_ui"]["status"] == "warning"


def test_self_protection_flags_open_permissions_and_tls_skip_verify(tmp_path):
    config = NulliusConfig()
    config.agent.tls_skip_verify = True

    config_path = tmp_path / "nullius.yaml"
    config_path.write_text("api: {}\n")
    agent_key = tmp_path / "agent.key"
    agent_key.write_text("secret")
    config_path.chmod(0o644)
    agent_key.chmod(0o644)

    result = evaluate_self_protection(config, config_path=str(config_path), agent_secret_present=True)
    codes = {item["code"]: item for item in result["checks"]}

    assert codes["config_permissions_open"]["status"] == "warning"
    assert codes["agent_key_permissions_open"]["severity"] == "critical"
    assert codes["agent_tls_skip_verify"]["status"] == "failing"
    assert result["failing_count"] >= 1


def test_self_protection_accepts_scoped_local_setup(tmp_path):
    config = NulliusConfig()
    config.api.cors_origins = ["http://localhost:3000"]
    config.api.require_bearer_auth = False
    config.api.require_ws_token = False

    config_path = tmp_path / "nullius.yaml"
    config_path.write_text("api: {}\n")
    agent_key = tmp_path / "agent.key"
    agent_key.write_text("secret")
    config_path.chmod(0o600)
    agent_key.chmod(0o600)

    result = evaluate_self_protection(config, config_path=str(config_path), agent_secret_present=True)

    assert result["level"] == "low"
    assert result["failing_count"] == 0


def test_self_protection_result_can_be_extended_with_primary_lock_signal(tmp_path):
    config = NulliusConfig()
    config.api.cors_origins = ["http://localhost:3000"]

    config_path = tmp_path / "nullius.yaml"
    config_path.write_text("api: {}\n")
    agent_key = tmp_path / "agent.key"
    agent_key.write_text("secret")
    config_path.chmod(0o600)
    agent_key.chmod(0o600)

    result = evaluate_self_protection(config, config_path=str(config_path), agent_secret_present=True)
    result["checks"].append({
        "code": "primary_lock_held",
        "status": "healthy",
        "severity": "low",
        "title": "Primary lock удерживается корректно",
        "description": "Тестовая запись для self-protection aggregation.",
        "recommendation": "Оставь lock-path на контролируемом storage.",
    })

    assert any(check["code"] == "primary_lock_held" for check in result["checks"])
