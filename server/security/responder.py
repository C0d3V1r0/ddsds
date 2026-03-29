# Политика реакции на угрозы: чистая функция без скрытого состояния.
# Держим её компактной и явной, чтобы поведение системы оставалось предсказуемым.

IMMEDIATE_BLOCK_TYPES = {"ssh_brute_force", "sqli", "command_injection"}
ESCALATABLE_MEDIUM_TYPES = {
    "path_traversal",
    "xss",
    "port_scan",
    "ssh_user_enum",
    "sensitive_path_probe",
    "scanner_probe",
}
CREDENTIAL_ABUSE_TYPES = {"ssh_brute_force", "ssh_user_enum", "web_login_bruteforce"}
RECONNAISSANCE_TYPES = {"port_scan", "sensitive_path_probe", "scanner_probe"}
ACTIVE_ATTACK_TYPES = {"sqli", "xss", "path_traversal", "command_injection"}


def _make_response(
    action: str,
    *,
    stage: str,
    reason: str,
    operator_priority: str,
    source_ip: str = "",
    highlight: bool = False,
) -> dict:
    payload = {
        "action": action,
        "stage": stage,
        "reason": reason,
        "operator_priority": operator_priority,
    }
    if source_ip:
        payload["ip"] = source_ip
    if action == "block":
        payload["highlight"] = highlight
    return payload


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
        return _make_response(
            "log",
            stage="observe",
            reason="observe_mode",
            operator_priority="low",
        )

    # Assist-режим сохраняет рекомендации оператору, но не делает auto-response.
    if operation_mode == "assist":
        if severity in ("medium", "high", "critical"):
            priority = "urgent" if severity == "critical" else "high" if severity == "high" else "normal"
            return _make_response(
                "review",
                stage="review",
                reason="assist_mode",
                operator_priority=priority,
            )
        return _make_response(
            "log",
            stage="observe",
            reason="log_only",
            operator_priority="low",
        )

    can_block = auto_block and bool(source_ip) and not cooldown_active

    # Critical — это уже не просто review, а немедленное containment.
    if severity == "critical" and can_block:
        return _make_response(
            "block",
            stage="block",
            reason="critical_severity",
            operator_priority="urgent",
            source_ip=source_ip,
            highlight=True,
        )

    # Высокие подтверждённые сигналы стараемся сдержать сразу,
    # но в trail отдельно помечаем это как containment.
    if severity == "high" and can_block:
        reason = "active_attack_high_confidence" if event_type in ACTIVE_ATTACK_TYPES else "high_severity_containment"
        return _make_response(
            "block",
            stage="contain",
            reason=reason,
            operator_priority="high",
            source_ip=source_ip,
        )

    # Отдельные типы угроз считаем достаточно опасными для автоблока с первого срабатывания.
    if event_type in IMMEDIATE_BLOCK_TYPES and can_block:
        reason = "credential_attack_first_seen" if event_type in CREDENTIAL_ABUSE_TYPES else "policy_block_on_first_seen"
        return _make_response(
            "block",
            stage="block",
            reason=reason,
            operator_priority="urgent",
            source_ip=source_ip,
            highlight=severity == "critical",
        )

    # Повторяющиеся medium-сигналы эскалируем по-разному:
    # credential abuse и reconnaissance становятся containment-кейсом,
    # а не просто ещё одним review.
    if (
        severity == "medium"
        and event_type in ESCALATABLE_MEDIUM_TYPES
        and recent_events_count >= medium_escalation_threshold
        and can_block
    ):
        if event_type in CREDENTIAL_ABUSE_TYPES:
            reason = "credential_attack_escalation"
        elif event_type in RECONNAISSANCE_TYPES:
            reason = "reconnaissance_escalation"
        else:
            reason = "medium_repetition_escalation"
        return _make_response(
            "block",
            stage="contain",
            reason=reason,
            operator_priority="high",
            source_ip=source_ip,
        )

    # Если блокировка была бы уместна, но cooldown ещё активен, не блокируем повторно.
    if cooldown_active and severity in ("medium", "high", "critical"):
        return _make_response(
            "review",
            stage="review",
            reason="cooldown_active",
            operator_priority="high" if severity in ("high", "critical") else "normal",
        )

    # Если сигнал опасный, но блок невозможен технически или политикой,
    # явно поднимаем его в ручной containment.
    if severity in ("high", "critical") and not can_block:
        return _make_response(
            "review",
            stage="review",
            reason="manual_containment_required",
            operator_priority="urgent" if severity == "critical" else "high",
        )

    if severity in ("medium", "high", "critical"):
        reason = "reconnaissance_review" if event_type in RECONNAISSANCE_TYPES else "operator_review"
        priority = "high" if severity == "high" else "normal"
        return _make_response(
            "review",
            stage="review",
            reason=reason,
            operator_priority=priority,
        )

    return _make_response(
        "log",
        stage="observe",
        reason="log_only",
        operator_priority="low",
    )
