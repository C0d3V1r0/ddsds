# Тесты baseline pipeline: отбор чистых окон, host-aware gates и maintenance filtering
from ml.baseline import build_baseline_dataset, get_effective_quality_gates


def _metric_rows(start_ts: int, count: int, step: int = 60) -> list[dict[str, int]]:
    return [{"timestamp": start_ts + index * step} for index in range(count)]


def test_builder_returns_clean_dataset_when_window_is_quiet():
    dataset = build_baseline_dataset(
        _metric_rows(1_700_000_000, 140),
        [{"timestamp": 1_700_000_120, "type": "xss", "severity": "low", "action_taken": "logged"}, {"timestamp": 1_700_000_360, "type": "xss", "severity": "low", "action_taken": "logged"}],
        min_samples=100,
        max_clean_events=10,
        filter_windows=(300, 180, 120, 60),
    )

    assert dataset["reason_code"] == "ready"
    assert dataset["clean_samples"] == 140
    assert dataset["discarded_samples"] == 0
    assert dataset["filter_window_seconds"] == 0
    assert dataset["quality_label"] == "high"
    assert dataset["noise_label"] == "clean"


def test_builder_prefers_filtered_baseline_when_noise_is_present():
    event_rows = [
        {"timestamp": 1_700_000_000 + index * 600, "type": "ssh_brute_force", "severity": "high", "action_taken": "review_required"}
        for index in range(25)
    ]
    dataset = build_baseline_dataset(
        _metric_rows(1_700_000_000, 180),
        event_rows,
        min_samples=100,
        max_clean_events=10,
        filter_windows=(300, 180, 120, 60),
    )

    assert dataset["reason_code"] == "ready_filtered_baseline"
    assert dataset["clean_samples"] >= 100
    assert dataset["discarded_samples"] > 0
    assert dataset["filter_window_seconds"] > 0
    assert dataset["quality_score"] > 0
    assert dataset["weighted_event_pressure"] > dataset["event_count"]


def test_builder_marks_insufficient_clean_data_when_best_subset_is_too_small():
    event_rows = [
        {"timestamp": 1_700_000_000 + index * 120, "type": "anomaly", "severity": "critical", "action_taken": "auto_block"}
        for index in range(50)
    ]
    dataset = build_baseline_dataset(
        _metric_rows(1_700_000_000, 120),
        event_rows,
        min_samples=100,
        max_clean_events=10,
        filter_windows=(300, 180, 120, 60),
    )

    assert dataset["reason_code"] == "insufficient_clean_data"
    assert 0 < dataset["clean_samples"] < 100
    assert dataset["discarded_samples"] > 0
    assert dataset["filter_window_seconds"] > 0
    assert dataset["quality_label"] in {"low", "medium"}
    assert dataset["noise_label"] == "noisy"


def test_host_profile_changes_effective_quality_gates():
    generic = get_effective_quality_gates(host_profile="generic", min_samples=100, max_clean_events=10)
    database = get_effective_quality_gates(host_profile="database", min_samples=100, max_clean_events=10)
    dev = get_effective_quality_gates(host_profile="dev", min_samples=100, max_clean_events=10)

    assert database[0] > generic[0]
    assert database[1] < generic[1]
    assert dev[0] < generic[0]
    assert dev[1] > generic[1]


def test_builder_filters_maintenance_windows_before_training():
    dataset = build_baseline_dataset(
        _metric_rows(1_700_000_000, 180),
        [],
        maintenance_timestamps=[1_700_000_000 + index * 900 for index in range(4)],
        min_samples=100,
        max_clean_events=10,
        filter_windows=(300, 180, 120, 60),
        host_profile="web",
        maintenance_window_seconds=300,
    )

    assert dataset["reason_code"] == "ready_filtered_baseline"
    assert dataset["maintenance_event_count"] == 4
    assert dataset["maintenance_window_seconds"] == 300
    assert dataset["discarded_samples"] > 0


def test_builder_uses_weighted_event_pressure_and_interval_merging():
    dataset = build_baseline_dataset(
        _metric_rows(1_700_000_000, 220),
        [
            {"timestamp": 1_700_000_300, "type": "anomaly", "severity": "critical", "action_taken": "auto_block"},
            {"timestamp": 1_700_000_360, "type": "anomaly", "severity": "critical", "action_taken": "auto_block"},
            {"timestamp": 1_700_000_420, "type": "sqli", "severity": "high", "action_taken": "review_required"},
        ],
        min_samples=100,
        max_clean_events=10,
        filter_windows=(300, 180, 120, 60),
    )

    assert dataset["weighted_event_pressure"] > dataset["event_count"]
    assert dataset["excluded_windows_count"] >= 1
