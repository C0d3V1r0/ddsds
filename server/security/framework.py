# Лёгкий detection framework для Nullius:
# здесь только типы и функции, без data-only классов.
from typing import Any, Callable, TypedDict


class DetectionContext(TypedDict):
    source: str
    line: str
    file: str
    now: int


DetectionRule = tuple[str, tuple[str, ...], Callable[[DetectionContext, dict[str, Any], Any], dict | None]]


def make_detection_context(*, source: str, line: str, file: str, now: int) -> DetectionContext:
    return {
        "source": source,
        "line": line,
        "file": file,
        "now": now,
    }


def make_detection_rule(
    name: str,
    *,
    sources: tuple[str, ...],
    detect: Callable[[DetectionContext, dict[str, Any], Any], dict | None],
) -> DetectionRule:
    return (name, sources, detect)


def run_detection_rules(
    context: DetectionContext,
    *,
    state: dict[str, Any],
    config: Any,
    rules: tuple[DetectionRule, ...],
) -> dict | None:
    """Прогоняет log entry по подходящим правилам и возвращает первое совпавшее событие."""
    for rule in rules:
        _name, sources, detect = rule
        if context["source"] not in sources:
            continue
        result = detect(context, state, config)
        if result is not None:
            return result
    return None
