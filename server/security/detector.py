# Детектор угроз: хранит только состояние SSH-окна, а остальная логика разложена на функции
import time
from collections import defaultdict
from dataclasses import dataclass, field

from config import SecurityConfig
from security.framework import DetectionContext, DetectionRule, make_detection_context, make_detection_rule, run_detection_rules
from security.rules import (
    FIREWALL_DEST_PORT_PATTERNS,
    FIREWALL_LOG_MARKERS,
    FIREWALL_SRC_PATTERNS,
    NGINX_LOG_IP_PATTERN,
    SSH_FAILED_PATTERN,
    WEB_ATTACK_PATTERNS,
)


def detect_log_event(
    log_entry: dict,
    *,
    config: SecurityConfig,
    state: dict,
    now: int | None = None,
) -> dict | None:
    """Маршрутизирует лог по общему реестру правил и возвращает первое найденное событие."""
    context = make_detection_context(
        source=str(log_entry.get("source", "")),
        line=str(log_entry.get("line", "")),
        file=str(log_entry.get("file", "")),
        now=int(time.time()) if now is None else now,
    )
    return run_detection_rules(context, state=state, config=config, rules=DETECTION_RULES)


def detect_auth_rule(context: DetectionContext, state: dict, config: SecurityConfig) -> dict | None:
    return detect_ssh_bruteforce(
        context["line"],
        ssh_attempts=state.setdefault("ssh_attempts", {}),
        threshold=config.ssh_brute_force.threshold,
        window=config.ssh_brute_force.window,
        now=context["now"],
    )


def detect_web_rule(context: DetectionContext, _state: dict, config: SecurityConfig) -> dict | None:
    return detect_web_attack(context["line"], enabled=config.web_attacks.enabled)


def detect_port_scan_rule(context: DetectionContext, state: dict, config: SecurityConfig) -> dict | None:
    return detect_port_scan(
        context["line"],
        scan_attempts=state.setdefault("port_scan_attempts", {}),
        enabled=config.port_scan.enabled,
        threshold=config.port_scan.unique_ports_threshold,
        window=config.port_scan.window,
        now=context["now"],
    )


def detect_ssh_bruteforce(
    line: str,
    *,
    ssh_attempts: dict[str, list[int]],
    threshold: int,
    window: int,
    now: int,
) -> dict | None:
    """Обнаружение brute-force по SSH: считаем попытки в скользящем окне."""
    match = SSH_FAILED_PATTERN.search(line)
    if not match:
        return None

    ip = match.group(1)
    ssh_attempts.setdefault(ip, []).append(now)
    ssh_attempts[ip] = _filter_timestamps_in_window(ssh_attempts[ip], now=now, window=window)
    _prune_stale_attempts(ssh_attempts, current_ip=ip, now=now, window=window)

    if len(ssh_attempts[ip]) >= threshold:
        # Сбрасываем счётчик после срабатывания, чтобы не дублировать алерты.
        ssh_attempts[ip] = []
        return {
            "type": "ssh_brute_force",
            "severity": "high",
            "source_ip": ip,
            "description": f"{threshold}+ failed SSH attempts in {window}s",
            "raw_log": line,
        }

    return None


def detect_web_attack(line: str, *, enabled: bool) -> dict | None:
    """Обнаружение веб-атак: SQLi, XSS, path traversal."""
    if not enabled:
        return None

    ip_match = NGINX_LOG_IP_PATTERN.search(line)
    source_ip = ip_match.group(1) if ip_match else ""

    for attack_type, pattern in WEB_ATTACK_PATTERNS.items():
        if pattern.search(line):
            severity = "high" if attack_type == "sqli" else "medium"
            return {
                "type": attack_type,
                "severity": severity,
                "source_ip": source_ip,
                "description": f"{attack_type} pattern detected",
                "raw_log": line,
            }

    return None


def detect_port_scan(
    line: str,
    *,
    scan_attempts: dict[str, list[tuple[int, int]]],
    enabled: bool,
    threshold: int,
    window: int,
    now: int,
) -> dict | None:
    """Обнаружение port scan по firewall/kernel логам через число уникальных destination ports."""
    if not enabled:
        return None
    if not any(marker in line for marker in FIREWALL_LOG_MARKERS):
        return None

    source_ip = _extract_first_match(line, FIREWALL_SRC_PATTERNS)
    dest_port_raw = _extract_first_match(line, FIREWALL_DEST_PORT_PATTERNS)
    if not source_ip or not dest_port_raw:
        return None

    dest_port = int(dest_port_raw)
    scan_attempts.setdefault(source_ip, []).append((now, dest_port))
    scan_attempts[source_ip] = _filter_port_hits_in_window(scan_attempts[source_ip], now=now, window=window)
    _prune_stale_port_scan_attempts(scan_attempts, current_ip=source_ip, now=now, window=window)

    unique_ports = sorted({port for _, port in scan_attempts[source_ip]})
    if len(unique_ports) < threshold:
        return None

    # После срабатывания сбрасываем окно, чтобы не штамповать дубликаты на каждой новой строке.
    scan_attempts[source_ip] = []
    severity = "high" if len(unique_ports) >= threshold * 2 else "medium"
    return {
        "type": "port_scan",
        "severity": severity,
        "source_ip": source_ip,
        "description": f"{len(unique_ports)} unique destination ports probed in {window}s",
        "raw_log": line,
    }


def _filter_timestamps_in_window(timestamps: list[int], *, now: int, window: int) -> list[int]:
    return [timestamp for timestamp in timestamps if now - timestamp <= window]


def _extract_first_match(line: str, patterns: tuple) -> str:
    for pattern in patterns:
        match = pattern.search(line)
        if match:
            return str(match.group(1))
    return ""


def _filter_port_hits_in_window(
    port_hits: list[tuple[int, int]],
    *,
    now: int,
    window: int,
) -> list[tuple[int, int]]:
    return [(timestamp, port) for timestamp, port in port_hits if now - timestamp <= window]


def _prune_stale_attempts(
    ssh_attempts: dict[str, list[int]],
    *,
    current_ip: str,
    now: int,
    window: int,
) -> None:
    """Ленивая очистка: удаляем устаревшие записи, чтобы словарь не рос бесконечно."""
    stale_ips: list[str] = []
    for other_ip, timestamps in ssh_attempts.items():
        if other_ip == current_ip:
            continue
        fresh = _filter_timestamps_in_window(timestamps, now=now, window=window)
        if not fresh:
            stale_ips.append(other_ip)
        else:
            ssh_attempts[other_ip] = fresh
    for stale_ip in stale_ips:
        del ssh_attempts[stale_ip]


def _prune_stale_port_scan_attempts(
    scan_attempts: dict[str, list[tuple[int, int]]],
    *,
    current_ip: str,
    now: int,
    window: int,
) -> None:
    stale_ips: list[str] = []
    for other_ip, port_hits in scan_attempts.items():
        if other_ip == current_ip:
            continue
        fresh = _filter_port_hits_in_window(port_hits, now=now, window=window)
        if not fresh:
            stale_ips.append(other_ip)
        else:
            scan_attempts[other_ip] = fresh
    for stale_ip in stale_ips:
        del scan_attempts[stale_ip]


DETECTION_RULES: tuple[DetectionRule, ...] = (
    make_detection_rule("ssh_brute_force", sources=("auth",), detect=detect_auth_rule),
    make_detection_rule("web_attacks", sources=("nginx", "apache"), detect=detect_web_rule),
    make_detection_rule("port_scan", sources=("firewall", "syslog"), detect=detect_port_scan_rule),
)


@dataclass(slots=True)
class Detector:
    config: SecurityConfig
    ssh_attempts: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    port_scan_attempts: dict[str, list[tuple[int, int]]] = field(default_factory=lambda: defaultdict(list))

    def check_log(self, log_entry: dict) -> dict | None:
        """Stateful-shell над чистыми detector-функциями."""
        return detect_log_event(
            log_entry,
            config=self.config,
            state={
                "ssh_attempts": self.ssh_attempts,
                "port_scan_attempts": self.port_scan_attempts,
            },
        )
