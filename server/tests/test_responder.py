# Тесты политики реакции: как severity и auto_block влияют на итоговое действие
from security.responder import decide_response


def test_low_severity_logs_only():
    action = decide_response({"severity": "low", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"
    assert action["stage"] == "observe"
    assert action["operator_priority"] == "low"


def test_medium_severity_logs():
    action = decide_response({"severity": "medium", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "review"
    assert action["stage"] == "review"
    assert action["reason"] == "operator_review"


def test_high_severity_blocks():
    action = decide_response({"severity": "high", "source_ip": "10.0.0.1", "type": "ssh_brute_force"})
    assert action["action"] == "block"
    assert action["ip"] == "10.0.0.1"
    assert action["stage"] == "contain"
    assert action["reason"] == "high_severity_containment"


def test_critical_severity_blocks():
    action = decide_response({"severity": "critical", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "block"
    assert action["highlight"] is True
    assert action["stage"] == "block"
    assert action["reason"] == "critical_severity"


def test_high_severity_no_block_when_disabled():
    action = decide_response({"severity": "high", "source_ip": "10.0.0.1", "type": "test"}, auto_block=False)
    assert action["action"] == "review"
    assert action["reason"] == "manual_containment_required"
    assert action["operator_priority"] == "high"


def test_no_block_without_ip():
    action = decide_response({"severity": "high", "source_ip": "", "type": "test"})
    assert action["action"] == "review"
    assert action["reason"] == "manual_containment_required"


def test_medium_path_traversal_escalates_after_repetition():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.9", "type": "path_traversal"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "block"
    assert action["reason"] == "medium_repetition_escalation"
    assert action["stage"] == "contain"


def test_medium_ssh_user_enum_escalates_after_repetition():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.10", "type": "ssh_user_enum"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "block"
    assert action["reason"] == "credential_attack_escalation"
    assert action["stage"] == "contain"


def test_medium_sensitive_path_probe_escalates_after_repetition():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.11", "type": "sensitive_path_probe"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "block"
    assert action["reason"] == "reconnaissance_escalation"
    assert action["stage"] == "contain"


def test_cooldown_prevents_repeat_block():
    action = decide_response(
        {"severity": "high", "source_ip": "10.0.0.9", "type": "ssh_brute_force"},
        cooldown_active=True,
    )
    assert action["action"] == "review"
    assert action["reason"] == "cooldown_active"
    assert action["stage"] == "review"


def test_observe_mode_never_blocks_or_reviews():
    action = decide_response(
        {"severity": "critical", "source_ip": "10.0.0.5", "type": "ssh_brute_force"},
        operation_mode="observe",
    )
    assert action["action"] == "log"
    assert action["reason"] == "observe_mode"
    assert action["stage"] == "observe"


def test_assist_mode_reviews_but_never_blocks():
    action = decide_response(
        {"severity": "high", "source_ip": "10.0.0.5", "type": "ssh_brute_force"},
        operation_mode="assist",
    )
    assert action["action"] == "review"
    assert action["reason"] == "assist_mode"
    assert action["stage"] == "review"
    assert action["operator_priority"] == "high"


def test_command_injection_high_confidence_gets_containment_reason():
    action = decide_response(
        {"severity": "high", "source_ip": "10.0.0.12", "type": "command_injection"},
    )
    assert action["action"] == "block"
    assert action["stage"] == "contain"
    assert action["reason"] == "active_attack_high_confidence"


def test_web_login_bruteforce_repetition_escalates_as_credential_attack():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.13", "type": "web_login_bruteforce"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "review"


def test_scanner_probe_without_threshold_stays_review():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.14", "type": "scanner_probe"},
        recent_events_count=2,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "review"
    assert action["reason"] == "reconnaissance_review"
