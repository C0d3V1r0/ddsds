from security.integration import merge_log_detection


def test_merge_log_detection_prefers_confirmed_rule_plus_ml_event():
    event = merge_log_detection(
        {
            "type": "path_traversal",
            "severity": "medium",
            "source_ip": "10.0.0.5",
            "description": "path_traversal pattern detected",
        },
        {"label": "path_traversal", "confidence": 1.0},
        raw_log="GET /../../etc/passwd",
    )

    assert event is not None
    assert event["description"] == "Rule+ML confirmed: path_traversal"
    assert event["severity"] == "high"


def test_merge_log_detection_falls_back_to_ml_when_rule_is_missing():
    event = merge_log_detection(
        None,
        {"label": "ssh_brute_force", "confidence": 1.0},
        raw_log="Failed password for root from 10.0.0.8 port 22 ssh2",
    )

    assert event is not None
    assert event["description"] == "ML-detected: ssh_brute_force"
    assert event["severity"] == "low"
