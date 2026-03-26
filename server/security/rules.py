# - Паттерны для обнаружения атак в логах
import re

# - SSH: извлекаем IP из записи о неудачной аутентификации
SSH_FAILED_PATTERN = re.compile(
    r"Failed password.*from\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)

# - Веб-атаки: SQL-инъекции, XSS, обход путей
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

# - Извлечение IP из начала строки лога nginx/apache
NGINX_LOG_IP_PATTERN = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
