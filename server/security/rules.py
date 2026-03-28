# Паттерны для обнаружения атак в логах
import re

# SSH: извлекаем IP из записи о неудачной аутентификации
SSH_FAILED_PATTERN = re.compile(
    r"Failed password.*from\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)

# Веб-атаки: SQL-инъекции, XSS, обход путей
WEB_ATTACK_PATTERNS = {
    "sqli": re.compile(
        r"(?i)(\b(union\s+select|or\s+1\s*=\s*1|and\s+1\s*=\s*1|"
        r"select\s+.*\s+from|insert\s+into|drop\s+table|"
        r";\s*delete\s+from|'\s*or\s*'|1\s*or\s*1))",
    ),
    "xss": re.compile(
        r"(?i)(<script|javascript:|on(load|error|click|mouseover)\s*=|"
        r"<img\s+[^>]*onerror|<svg\s+[^>]*onload)",
    ),
    "path_traversal": re.compile(
        r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f){2,}",
    ),
}

# Извлечение IP из начала строки лога nginx/apache
NGINX_LOG_IP_PATTERN = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

# Firewall / kernel / UFW / nftables: эти записи позволяют увидеть сканирование портов
# по числу уникальных destination ports в коротком временном окне.
FIREWALL_SRC_PATTERNS = (
    re.compile(r"\bSRC=(\d{1,3}(?:\.\d{1,3}){3})\b"),
    re.compile(r"\bSRC=([0-9a-fA-F:]+)\b"),
    re.compile(r"\bfrom\s+(\d{1,3}(?:\.\d{1,3}){3})\b", re.IGNORECASE),
)
FIREWALL_DEST_PORT_PATTERNS = (
    re.compile(r"\bDPT=(\d{1,5})\b"),
    re.compile(r"\bDSTPORT=(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\bdport\s+(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\bto\s+port\s+(\d{1,5})\b", re.IGNORECASE),
)
FIREWALL_LOG_MARKERS = (
    "UFW BLOCK",
    "UFW AUDIT",
    "iptables",
    "nftables",
    "NULLIUS_PORTSCAN",
    "kernel:",
)
