# Общая политика доставки уведомлений для внешних интеграций.
import re
import time

SEVERITY_RANKS = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def normalize_notify_min_severity(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in SEVERITY_RANKS:
        return normalized
    return "high"


def normalize_quiet_time(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if not _TIME_RE.match(normalized):
        raise RuntimeError("Quiet hours time must use HH:MM format")

    hours, minutes = normalized.split(":", maxsplit=1)
    if int(hours) > 23 or int(minutes) > 59:
        raise RuntimeError("Quiet hours time is invalid")
    return normalized


def quiet_hours_active(start: str, end: str, now: int | None = None) -> bool:
    if not start or not end or start == end:
        return False

    current_struct = time.localtime(now or time.time())
    current_minutes = current_struct.tm_hour * 60 + current_struct.tm_min
    start_minutes = _parse_minutes(start)
    end_minutes = _parse_minutes(end)

    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def should_notify_by_policy(
    settings: dict[str, object],
    event: dict[str, object],
    now: int | None = None,
) -> bool:
    action_taken = str(event.get("action_taken", "") or "")
    if action_taken == "auto_block":
        return bool(settings.get("notify_auto_block"))

    if not bool(settings.get("notify_high_severity")):
        return False

    if quiet_hours_active(
        str(settings.get("quiet_hours_start", "") or ""),
        str(settings.get("quiet_hours_end", "") or ""),
        now=now,
    ):
        return False

    severity = str(event.get("severity", "") or "low").lower()
    current_rank = SEVERITY_RANKS.get(severity, 0)
    min_rank = SEVERITY_RANKS[normalize_notify_min_severity(str(settings.get("notify_min_severity", "high") or "high"))]
    return current_rank >= min_rank


def _parse_minutes(value: str) -> int:
    hours, minutes = value.split(":", maxsplit=1)
    return int(hours) * 60 + int(minutes)
