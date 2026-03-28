# Подготовка clean baseline для anomaly detector: фильтрация шумных окон и оценка качества датасета
from typing import TypedDict

import aiosqlite


class BaselineDataset(TypedDict):
    rows: list[aiosqlite.Row]
    total_samples: int
    clean_samples: int
    discarded_samples: int
    event_count: int
    maintenance_event_count: int
    filter_window_seconds: int
    maintenance_window_seconds: int
    quality_score: int
    quality_label: str
    noise_label: str
    reason_code: str
    host_profile: str
    required_samples: int
    max_clean_events: int
    weighted_event_pressure: int
    excluded_windows_count: int


def _baseline_dataset(**data: object) -> BaselineDataset:
    """Собирает результат как простую структуру данных без поведения и методов."""
    return BaselineDataset(**data)


HOST_PROFILE_RULES: dict[str, dict[str, float]] = {
    "generic": {"sample_multiplier": 1.0, "event_tolerance": 1.0},
    "web": {"sample_multiplier": 1.15, "event_tolerance": 0.8},
    "docker": {"sample_multiplier": 1.1, "event_tolerance": 0.85},
    "database": {"sample_multiplier": 1.25, "event_tolerance": 0.7},
    "dev": {"sample_multiplier": 0.85, "event_tolerance": 1.3},
}


def get_effective_quality_gates(
    *,
    host_profile: str,
    min_samples: int,
    max_clean_events: int,
) -> tuple[int, int]:
    rules = HOST_PROFILE_RULES.get(host_profile, HOST_PROFILE_RULES["generic"])
    effective_min_samples = max(50, int(round(min_samples * rules["sample_multiplier"])))
    effective_max_clean_events = max(1, int(round(max_clean_events * rules["event_tolerance"])))
    return effective_min_samples, effective_max_clean_events


def build_baseline_dataset(
    rows: list[aiosqlite.Row],
    event_rows: list[aiosqlite.Row | dict | int],
    *,
    maintenance_timestamps: list[int] | None = None,
    min_samples: int,
    max_clean_events: int,
    filter_windows: tuple[int, ...],
    host_profile: str = "generic",
    maintenance_window_seconds: int = 900,
) -> BaselineDataset:
    """Строит clean dataset для обучения anomaly detector.

    Это функциональное ядро без скрытого состояния:
    на входе сырые метрики и таймстемпы security events,
    на выходе готовый baseline и его quality-метрики.
    """
    total_samples = len(rows)
    event_windows = _build_event_windows(event_rows, base_buffer_seconds=max(filter_windows, default=0))
    event_count = len(event_windows)
    maintenance_timestamps = maintenance_timestamps or []
    maintenance_event_count = len(maintenance_timestamps)
    weighted_event_pressure = int(round(sum(window["weight"] for window in event_windows)))
    effective_min_samples, effective_max_clean_events = get_effective_quality_gates(
        host_profile=host_profile,
        min_samples=min_samples,
        max_clean_events=max_clean_events,
    )

    if total_samples == 0:
        return _baseline_dataset(
            rows=[],
            total_samples=0,
            clean_samples=0,
            discarded_samples=0,
            event_count=event_count,
            maintenance_event_count=maintenance_event_count,
            filter_window_seconds=0,
            maintenance_window_seconds=maintenance_window_seconds,
            quality_score=0,
            quality_label="low",
            noise_label="noisy",
            reason_code="insufficient_data",
            host_profile=host_profile,
            required_samples=effective_min_samples,
            max_clean_events=effective_max_clean_events,
            weighted_event_pressure=weighted_event_pressure,
            excluded_windows_count=0,
        )

    maintenance_intervals = _build_maintenance_windows(maintenance_timestamps, maintenance_window_seconds)
    maintenance_filtered_rows = _filter_rows_outside_intervals(rows, maintenance_intervals)
    maintenance_discarded = total_samples - len(maintenance_filtered_rows)

    if weighted_event_pressure <= effective_max_clean_events and len(maintenance_filtered_rows) >= effective_min_samples:
        quality_score = _compute_quality_score(
            total_samples=total_samples,
            clean_samples=len(maintenance_filtered_rows),
            weighted_event_pressure=weighted_event_pressure,
            maintenance_event_count=maintenance_event_count,
            min_samples=effective_min_samples,
            max_clean_events=effective_max_clean_events,
        )
        return _baseline_dataset(
            rows=list(maintenance_filtered_rows),
            total_samples=total_samples,
            clean_samples=len(maintenance_filtered_rows),
            discarded_samples=maintenance_discarded,
            event_count=event_count,
            maintenance_event_count=maintenance_event_count,
            filter_window_seconds=0,
            maintenance_window_seconds=maintenance_window_seconds,
            quality_score=quality_score,
            quality_label=_quality_label(quality_score),
            noise_label=_noise_label(weighted_event_pressure, effective_max_clean_events),
            reason_code="ready" if maintenance_discarded == 0 else "ready_filtered_baseline",
            host_profile=host_profile,
            required_samples=effective_min_samples,
            max_clean_events=effective_max_clean_events,
            weighted_event_pressure=weighted_event_pressure,
            excluded_windows_count=len(maintenance_intervals),
        )

    best_rows: list[aiosqlite.Row] = []
    best_window = 0
    best_score = -1
    best_intervals_count = len(maintenance_intervals)
    for window_seconds in filter_windows:
        event_intervals = _build_effective_event_intervals(event_windows, fallback_window=window_seconds)
        filtered_rows = _filter_rows_outside_intervals(maintenance_filtered_rows, event_intervals)
        quality_score = _compute_quality_score(
            total_samples=total_samples,
            clean_samples=len(filtered_rows),
            weighted_event_pressure=weighted_event_pressure,
            maintenance_event_count=maintenance_event_count,
            min_samples=effective_min_samples,
            max_clean_events=effective_max_clean_events,
        )
        if quality_score > best_score or (
            quality_score == best_score and len(filtered_rows) > len(best_rows)
        ):
            best_rows = filtered_rows
            best_window = window_seconds
            best_score = quality_score
            best_intervals_count = len(event_intervals) + len(maintenance_intervals)
        if len(filtered_rows) >= effective_min_samples:
            return _baseline_dataset(
                rows=filtered_rows,
                total_samples=total_samples,
                clean_samples=len(filtered_rows),
                discarded_samples=total_samples - len(filtered_rows),
                event_count=event_count,
                maintenance_event_count=maintenance_event_count,
                filter_window_seconds=window_seconds,
                maintenance_window_seconds=maintenance_window_seconds,
                quality_score=quality_score,
                quality_label=_quality_label(quality_score),
                noise_label=_noise_label(weighted_event_pressure, effective_max_clean_events),
                reason_code="ready_filtered_baseline",
                host_profile=host_profile,
                required_samples=effective_min_samples,
                max_clean_events=effective_max_clean_events,
                weighted_event_pressure=weighted_event_pressure,
                excluded_windows_count=len(event_intervals) + len(maintenance_intervals),
            )

    if not best_rows:
        return _baseline_dataset(
            rows=[],
            total_samples=total_samples,
            clean_samples=0,
            discarded_samples=total_samples,
            event_count=event_count,
            maintenance_event_count=maintenance_event_count,
            filter_window_seconds=0,
            maintenance_window_seconds=maintenance_window_seconds,
            quality_score=0,
            quality_label="low",
            noise_label="noisy",
            reason_code="poisoned_baseline",
            host_profile=host_profile,
            required_samples=effective_min_samples,
            max_clean_events=effective_max_clean_events,
            weighted_event_pressure=weighted_event_pressure,
            excluded_windows_count=best_intervals_count,
        )

    return _baseline_dataset(
        rows=best_rows,
        total_samples=total_samples,
        clean_samples=len(best_rows),
        discarded_samples=total_samples - len(best_rows),
        event_count=event_count,
        maintenance_event_count=maintenance_event_count,
        filter_window_seconds=best_window,
        maintenance_window_seconds=maintenance_window_seconds,
        quality_score=max(best_score, 0),
        quality_label=_quality_label(max(best_score, 0)),
        noise_label=_noise_label(weighted_event_pressure, effective_max_clean_events),
        reason_code="insufficient_clean_data",
        host_profile=host_profile,
        required_samples=effective_min_samples,
        max_clean_events=effective_max_clean_events,
        weighted_event_pressure=weighted_event_pressure,
        excluded_windows_count=best_intervals_count,
    )


def _build_event_windows(
    event_rows: list[aiosqlite.Row | dict | int],
    *,
    base_buffer_seconds: int,
) -> list[dict[str, int | float]]:
    windows: list[dict[str, int | float]] = []
    for raw_event in event_rows:
        if isinstance(raw_event, int):
            timestamp = raw_event
            severity = "medium"
            event_type = ""
            action_taken = ""
        elif hasattr(raw_event, "keys"):
            timestamp = int(raw_event["timestamp"])
            severity = str(raw_event["severity"]) if "severity" in raw_event.keys() else "medium"
            event_type = str(raw_event["type"]) if "type" in raw_event.keys() else ""
            action_taken = str(raw_event["action_taken"]) if "action_taken" in raw_event.keys() else ""
        else:
            timestamp = int(raw_event[0])
            event_type = str(raw_event[1]) if len(raw_event) > 1 else ""
            severity = str(raw_event[2]) if len(raw_event) > 2 else "medium"
            action_taken = str(raw_event[3]) if len(raw_event) > 3 else ""

        buffer_multiplier = (
            _severity_buffer_multiplier(severity)
            * _event_type_buffer_multiplier(event_type)
            * _action_buffer_multiplier(action_taken)
        )
        windows.append({
            "timestamp": timestamp,
            "buffer_seconds": max(30, int(round(base_buffer_seconds * buffer_multiplier))),
            "weight": _event_weight(severity, event_type, action_taken),
        })
    return windows


def _build_effective_event_intervals(
    event_windows: list[dict[str, int | float]],
    *,
    fallback_window: int,
) -> list[tuple[int, int]]:
    intervals = []
    for event in event_windows:
        ts = int(event["timestamp"])
        buffer_seconds = max(30, min(fallback_window, int(event["buffer_seconds"])))
        intervals.append((ts - buffer_seconds, ts + buffer_seconds))
    return _merge_intervals(intervals)


def _build_maintenance_windows(
    maintenance_timestamps: list[int],
    maintenance_window_seconds: int,
) -> list[tuple[int, int]]:
    return _merge_intervals([
        (timestamp - maintenance_window_seconds, timestamp + maintenance_window_seconds)
        for timestamp in maintenance_timestamps
    ])


def _filter_rows_outside_intervals(
    rows: list[aiosqlite.Row],
    intervals: list[tuple[int, int]],
) -> list[aiosqlite.Row]:
    if not intervals:
        return list(rows)

    filtered: list[aiosqlite.Row] = []
    interval_index = 0
    intervals_count = len(intervals)
    for row in rows:
        ts = int(row["timestamp"])
        while interval_index < intervals_count and intervals[interval_index][1] < ts:
            interval_index += 1
        if interval_index < intervals_count and intervals[interval_index][0] <= ts <= intervals[interval_index][1]:
            continue
        filtered.append(row)
    return filtered


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals.sort()
    merged: list[tuple[int, int]] = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _compute_quality_score(
    *,
    total_samples: int,
    clean_samples: int,
    weighted_event_pressure: int,
    maintenance_event_count: int,
    min_samples: int,
    max_clean_events: int,
) -> int:
    if total_samples <= 0:
        return 0

    clean_ratio = clean_samples / total_samples
    # Чем ближе к лимиту шумовых событий, тем осторожнее доверяем baseline.
    allowed_pressure = max(max_clean_events, 1)
    pressure_penalty = min(weighted_event_pressure / allowed_pressure, 3.0)
    pressure_score = max(0.0, 1.0 - (pressure_penalty / 3.0))
    maintenance_penalty = min(maintenance_event_count / 5.0, 1.0)
    maintenance_score = max(0.0, 1.0 - maintenance_penalty)
    sample_score = min(clean_samples / max(min_samples, 1), 1.0)

    score = int((clean_ratio * 45) + (pressure_score * 20) + (sample_score * 25) + (maintenance_score * 10))
    return max(0, min(score, 100))


def _quality_label(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _noise_label(weighted_event_pressure: int, max_clean_events: int) -> str:
    if weighted_event_pressure <= max(max_clean_events // 2, 1):
        return "clean"
    if weighted_event_pressure <= max_clean_events:
        return "stressed"
    return "noisy"


def _severity_buffer_multiplier(severity: str) -> float:
    return {
        "low": 0.6,
        "medium": 0.9,
        "high": 1.1,
        "critical": 1.4,
    }.get(severity, 1.0)


def _event_type_buffer_multiplier(event_type: str) -> float:
    return {
        "anomaly": 1.3,
        "sqli": 1.15,
        "port_scan": 1.0,
        "ssh_brute_force": 0.9,
        "xss": 0.75,
        "path_traversal": 1.0,
    }.get(event_type, 1.0)


def _action_buffer_multiplier(action_taken: str) -> float:
    return {
        "auto_block": 1.3,
        "review_required": 1.0,
        "logged": 0.8,
    }.get(action_taken, 1.0)


def _event_weight(severity: str, event_type: str, action_taken: str) -> float:
    severity_weight = {
        "low": 0.5,
        "medium": 1.0,
        "high": 1.7,
        "critical": 2.3,
    }.get(severity, 1.0)
    type_weight = {
        "anomaly": 1.5,
        "sqli": 1.4,
        "port_scan": 1.2,
        "ssh_brute_force": 1.0,
        "xss": 0.8,
        "path_traversal": 0.9,
    }.get(event_type, 1.0)
    action_weight = {
        "auto_block": 1.2,
        "review_required": 1.0,
        "logged": 0.85,
    }.get(action_taken, 1.0)
    return severity_weight * type_weight * action_weight
