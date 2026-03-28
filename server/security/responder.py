# Политика реакции на угрозы: чистая функция без скрытого состояния

BLOCK_ON_FIRST_SEEN_TYPES = {"ssh_brute_force", "sqli"}
ESCALATABLE_MEDIUM_TYPES = {
    "path_traversal",
    "xss",
    "port_scan",
    "ssh_user_enum",
    "sensitive_path_probe",
}


def decide_response(
    event: dict,
    *,
    operation_mode: str = "auto_defend",
    auto_block: bool = True,
    recent_events_count: int = 1,
    medium_escalation_threshold: int = 3,
    cooldown_active: bool = False,
) -> dict:
    """Принимает решение по событию на основе severity, типа угрозы и контекста повторяемости."""
    event_type = str(event.get("type", ""))
    severity = str(event.get("severity", "low"))
    source_ip = str(event.get("source_ip", ""))
    operation_mode = str(operation_mode or "auto_defend").strip().lower()

    # Observe-режим принципиально пассивный: ничего не блокируем и не эскалируем.
    if operation_mode == "observe":
        return {"action": "log", "reason": "observe_mode"}

    # Assist-режим сохраняет рекомендации оператору, но не делает auto-response.
    if operation_mode == "assist":
        if severity in ("medium", "high", "critical"):
            return {"action": "review", "reason": "assist_mode"}
        return {"action": "log", "reason": "log_only"}

    can_block = auto_block and bool(source_ip) and not cooldown_active

    # Подтверждённые high/critical угрозы с IP блокируем сразу.
    if severity in ("high", "critical") and can_block:
        return {
            "action": "block",
            "ip": source_ip,
            "highlight": severity == "critical",
            "reason": "high_severity",
        }

    # Отдельные типы угроз считаем достаточно опасными для автоблока с первого срабатывания.
    if event_type in BLOCK_ON_FIRST_SEEN_TYPES and can_block:
        return {
            "action": "block",
            "ip": source_ip,
            "highlight": severity == "critical",
            "reason": "policy_block_on_first_seen",
        }

    # Повторяющиеся medium-события от одного IP эскалируем до автоблока.
    if (
        severity == "medium"
        and event_type in ESCALATABLE_MEDIUM_TYPES
        and recent_events_count >= medium_escalation_threshold
        and can_block
    ):
        return {
            "action": "block",
            "ip": source_ip,
            "highlight": False,
            "reason": "medium_repetition_escalation",
        }

    # Если блокировка была бы уместна, но cooldown ещё активен, не блокируем повторно.
    if cooldown_active and severity in ("medium", "high", "critical"):
        return {"action": "review", "reason": "cooldown_active"}

    if severity in ("medium", "high", "critical"):
        return {"action": "review", "reason": "operator_review"}

    return {"action": "log", "reason": "log_only"}
