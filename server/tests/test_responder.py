# Тесты политики реакции: как severity и auto_block влияют на итоговое действие
from security.responder import decide_response


def test_low_severity_logs_only():
    action = decide_response({"severity": "low", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"


def test_medium_severity_logs():
    action = decide_response({"severity": "medium", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "review"


def test_high_severity_blocks():
    action = decide_response({"severity": "high", "source_ip": "10.0.0.1", "type": "ssh_brute_force"})
    assert action["action"] == "block"
    assert action["ip"] == "10.0.0.1"


def test_critical_severity_blocks():
    action = decide_response({"severity": "critical", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "block"
    assert action["highlight"] is True


def test_high_severity_no_block_when_disabled():
    action = decide_response({"severity": "high", "source_ip": "10.0.0.1", "type": "test"}, auto_block=False)
    assert action["action"] == "review"


def test_no_block_without_ip():
    action = decide_response({"severity": "high", "source_ip": "", "type": "test"})
    assert action["action"] == "review"


def test_medium_path_traversal_escalates_after_repetition():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.9", "type": "path_traversal"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "block"
    assert action["reason"] == "medium_repetition_escalation"


def test_medium_ssh_user_enum_escalates_after_repetition():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.10", "type": "ssh_user_enum"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "block"
    assert action["reason"] == "medium_repetition_escalation"


def test_medium_sensitive_path_probe_escalates_after_repetition():
    action = decide_response(
        {"severity": "medium", "source_ip": "10.0.0.11", "type": "sensitive_path_probe"},
        recent_events_count=3,
        medium_escalation_threshold=3,
    )
    assert action["action"] == "block"
    assert action["reason"] == "medium_repetition_escalation"


def test_cooldown_prevents_repeat_block():
    action = decide_response(
        {"severity": "high", "source_ip": "10.0.0.9", "type": "ssh_brute_force"},
        cooldown_active=True,
    )
    assert action["action"] == "review"
    assert action["reason"] == "cooldown_active"


def test_observe_mode_never_blocks_or_reviews():
    action = decide_response(
        {"severity": "critical", "source_ip": "10.0.0.5", "type": "ssh_brute_force"},
        operation_mode="observe",
    )
    assert action["action"] == "log"
    assert action["reason"] == "observe_mode"


def test_assist_mode_reviews_but_never_blocks():
    action = decide_response(
        {"severity": "high", "source_ip": "10.0.0.5", "type": "ssh_brute_force"},
        operation_mode="assist",
    )
    assert action["action"] == "review"
    assert action["reason"] == "assist_mode"
