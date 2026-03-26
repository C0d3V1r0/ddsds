# Детектор угроз: анализирует записи логов и выявляет атаки
import time
from collections import defaultdict

from config import SecurityConfig
from security.rules import SSH_FAILED_PATTERN, WEB_ATTACK_PATTERNS, NGINX_LOG_IP_PATTERN


class Detector:
    def __init__(self, config: SecurityConfig):
        self.config = config
        self._ssh_attempts: dict[str, list[int]] = defaultdict(list)

    def check_log(self, log_entry: dict) -> dict | None:
        """Главная точка входа: маршрутизирует лог по источнику"""
        source = log_entry.get("source", "")
        line = log_entry.get("line", "")

        if source == "auth":
            return self._check_ssh(line)
        if source in ("nginx", "apache"):
            return self._check_web(line)

        return None

    def _check_ssh(self, line: str) -> dict | None:
        """Обнаружение brute-force по SSH: считаем попытки в скользящем окне"""
        match = SSH_FAILED_PATTERN.search(line)
        if not match:
            return None

        ip = match.group(1)
        now = int(time.time())
        window = self.config.ssh_brute_force.window
        threshold = self.config.ssh_brute_force.threshold

        self._ssh_attempts[ip].append(now)
        # Оставляем только попытки внутри временного окна
        self._ssh_attempts[ip] = [t for t in self._ssh_attempts[ip] if now - t <= window]

        # Ленивая очистка: удаляем устаревшие записи для предотвращения утечки памяти
        stale_ips = []
        for other_ip, timestamps in self._ssh_attempts.items():
            if other_ip == ip:
                continue
            fresh = [t for t in timestamps if now - t <= window]
            if not fresh:
                stale_ips.append(other_ip)
            else:
                self._ssh_attempts[other_ip] = fresh
        for stale_ip in stale_ips:
            del self._ssh_attempts[stale_ip]

        if len(self._ssh_attempts[ip]) >= threshold:
            # Сбрасываем счётчик после срабатывания, чтобы не дублировать алерты
            self._ssh_attempts[ip] = []
            return {
                "type": "ssh_brute_force",
                "severity": "high",
                "source_ip": ip,
                "description": f"{threshold}+ failed SSH attempts in {window}s",
                "raw_log": line,
            }

        return None

    def _check_web(self, line: str) -> dict | None:
        """Обнаружение веб-атак: SQLi, XSS, path traversal"""
        if not self.config.web_attacks.enabled:
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
