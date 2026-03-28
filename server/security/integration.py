# Интеграция сигналов детектора и ML в единый security event.
# Здесь держим только функциональную логику без runtime-состояния.


def merge_log_detection(
    rule_event: dict | None,
    ml_event: dict | None,
    *,
    raw_log: str,
    ml_min_confidence: float = 0.6,
) -> dict | None:
    """Сводит rule-based и ML сигналы к одному каноническому событию.

    Приоритеты:
    - rule + ML с одинаковым типом => подтверждённый сигнал с повышенной уверенностью
    - только rule => отдаём rule-событие как есть
    - только ML => создаём мягкое review-событие
    """
    strong_ml_event = _strong_ml_signal(ml_event, ml_min_confidence)

    if rule_event is not None and strong_ml_event is not None and rule_event.get("type") == strong_ml_event.get("label"):
        merged = dict(rule_event)
        merged["description"] = f"Rule+ML confirmed: {rule_event['type']}"
        merged["severity"] = _boost_severity(str(rule_event.get("severity", "medium")))
        merged["raw_log"] = raw_log
        return merged

    if rule_event is not None:
        merged = dict(rule_event)
        merged["raw_log"] = raw_log
        return merged

    if strong_ml_event is not None:
        return {
            "type": strong_ml_event["label"],
            "severity": "low",
            "source_ip": "",
            "description": f"ML-detected: {strong_ml_event['label']}",
            "raw_log": raw_log,
            "action_taken": "review_required",
        }

    return None


def _strong_ml_signal(ml_event: dict | None, min_confidence: float) -> dict | None:
    """Отсекает слабые и служебные ML-результаты до общего merge-пайплайна."""
    if ml_event is None:
        return None

    label = str(ml_event.get("label", "unknown")).strip()
    confidence = float(ml_event.get("confidence", 0.0) or 0.0)
    if label in {"", "normal", "unknown"}:
        return None
    if confidence < min_confidence:
        return None
    return {"label": label, "confidence": confidence}


def _boost_severity(severity: str) -> str:
    order = ("low", "medium", "high", "critical")
    try:
        index = order.index(severity)
    except ValueError:
        return severity
    return order[min(index + 1, len(order) - 1)]
