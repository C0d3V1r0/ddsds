# Тесты интеграции rule-based и ML detection в единый security event.
from security.integration import merge_log_detection


def test_merge_log_detection_confirms_matching_rule_and_ml():
    event = merge_log_detection(
        {
            "type": "ssh_brute_force",
            "severity": "high",
            "source_ip": "203.0.113.7",
            "description": "5 failed attempts",
        },
        {"label": "ssh_brute_force", "confidence": 0.91},
        raw_log="Failed password for root",
        ml_min_confidence=0.6,
    )

    assert event is not None
    assert event["description"] == "Rule+ML confirmed: ssh_brute_force"
    assert event["severity"] == "critical"
    assert event["source_ip"] == "203.0.113.7"


def test_merge_log_detection_ignores_weak_ml_signal():
    event = merge_log_detection(
        None,
        {"label": "ssh_brute_force", "confidence": 0.41},
        raw_log="Failed password for root",
        ml_min_confidence=0.6,
    )

    assert event is None


def test_merge_log_detection_keeps_rule_when_ml_disagrees():
    event = merge_log_detection(
        {
            "type": "path_traversal",
            "severity": "medium",
            "source_ip": "198.51.100.4",
            "description": "path_traversal pattern detected",
        },
        {"label": "sqli", "confidence": 0.92},
        raw_log="GET /../../etc/passwd",
        ml_min_confidence=0.6,
    )

    assert event is not None
    assert event["type"] == "path_traversal"
    assert event["description"] == "path_traversal pattern detected"


def test_merge_log_detection_creates_ml_only_event_when_signal_is_strong():
    event = merge_log_detection(
        None,
        {"label": "xss", "confidence": 0.88},
        raw_log="198.51.100.24 - - [28/Mar/2026:12:00:00 +0000] \"GET /search?q=<script>alert(1)</script> HTTP/1.1\" 200 42",
        ml_min_confidence=0.6,
    )

    assert event is not None
    assert event["type"] == "xss"
    assert event["description"] == "ML-detected: xss"
    assert event["action_taken"] == "review_required"
    assert event["source_ip"] == "198.51.100.24"
    assert event["severity"] == "low"
