#!/usr/bin/env bash
set -euo pipefail

# - Установка Nullius — self-hosted security platform
# - Идемпотентный скрипт: безопасен для повторного запуска

INSTALL_DIR="/opt/nullius"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ============================================================
# - Вспомогательные функции
# ============================================================

log_step() {
    echo ""
    echo "[$1] $2"
}

fail() {
    echo "ОШИБКА: $1" >&2
    exit 1
}

# ============================================================
# - Проверки перед установкой
# ============================================================

log_step "0/10" "Проверка окружения..."

# - Только root
if [[ $EUID -ne 0 ]]; then
    fail "Запустите от root: sudo bash install.sh"
fi

# - Только Ubuntu/Debian
if ! grep -qiE 'ubuntu|debian' /etc/os-release 2>/dev/null; then
    fail "Поддерживаются только Ubuntu и Debian"
fi

# - Определение архитектуры
ARCH="$(dpkg --print-architecture 2>/dev/null || uname -m)"
case "$ARCH" in
    amd64|x86_64) AGENT_BINARY="nullius-agent-amd64" ;;
    arm64|aarch64) AGENT_BINARY="nullius-agent-arm64" ;;
    *) fail "Неподдерживаемая архитектура: $ARCH" ;;
esac

echo "  ОС: $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "  Архитектура: $ARCH"

# ============================================================
# - 1. Системные зависимости
# ============================================================

log_step "1/10" "Установка зависимостей..."

apt-get update -qq
apt-get install -y -qq nginx python3 python3-venv python3-pip openssl apache2-utils > /dev/null

# ============================================================
# - 2. Системный пользователь
# ============================================================

log_step "2/10" "Системный пользователь..."

if id nullius &>/dev/null; then
    echo "  Пользователь nullius уже существует"
else
    useradd --system --no-create-home --shell /usr/sbin/nologin nullius
    echo "  Создан пользователь nullius"
fi

# ============================================================
# - 3. Структура директорий
# ============================================================

log_step "3/10" "Создание директорий..."

mkdir -p "$INSTALL_DIR"/{bin,config/tls,data,logs,server,web,models}

# ============================================================
# - 4. Установка Go агента
# ============================================================

log_step "4/10" "Установка агента ($AGENT_BINARY)..."

if [[ -f "$SCRIPT_DIR/$AGENT_BINARY" ]]; then
    cp "$SCRIPT_DIR/$AGENT_BINARY" "$INSTALL_DIR/bin/nullius-agent"
    chmod 755 "$INSTALL_DIR/bin/nullius-agent"
else
    echo "  ВНИМАНИЕ: бинарник $AGENT_BINARY не найден, пропуск"
fi

# - Верификация контрольных сумм
if [[ -f "$SCRIPT_DIR/checksums.sha256" ]]; then
    log_step "4.1" "Проверяю контрольные суммы..."
    (cd "$SCRIPT_DIR" && sha256sum -c checksums.sha256) || fail "Контрольные суммы не совпадают — возможна подмена дистрибутива"
fi

# ============================================================
# - 5. Установка Python server
# ============================================================

log_step "5/10" "Установка сервера..."

if [[ -f "$SCRIPT_DIR/server.tar.gz" ]]; then
    # - Безопасная распаковка сервера
    tar tzf "$SCRIPT_DIR/server.tar.gz" | grep -qE '^\.\./|^/' && fail "Подозрительные пути в архиве"
    tar xzf "$SCRIPT_DIR/server.tar.gz" -C "$INSTALL_DIR/"

    # - Создание venv если его нет
    if [[ ! -d "$INSTALL_DIR/server/venv" ]]; then
        python3 -m venv "$INSTALL_DIR/server/venv"
    fi

    # - Установка зависимостей если requirements.txt существует
    if [[ -f "$INSTALL_DIR/server/requirements.txt" ]]; then
        "$INSTALL_DIR/server/venv/bin/pip" install --quiet --upgrade pip
        "$INSTALL_DIR/server/venv/bin/pip" install --quiet -r "$INSTALL_DIR/server/requirements.txt"
    fi
else
    echo "  ВНИМАНИЕ: server.tar.gz не найден, пропуск"
fi

# ============================================================
# - 6. Установка фронтенда
# ============================================================

log_step "6/10" "Установка фронтенда..."

if [[ -d "$SCRIPT_DIR/web" ]]; then
    cp -r "$SCRIPT_DIR/web/." "$INSTALL_DIR/web/"
else
    echo "  ВНИМАНИЕ: директория web не найдена, пропуск"
fi

# ============================================================
# - 7. Генерация конфигурации и секретов
# ============================================================

log_step "7/10" "Генерация конфигурации..."

# - Agent shared secret
if [[ ! -f "$INSTALL_DIR/config/agent.key" ]]; then
    AGENT_SECRET=$(openssl rand -hex 32)
    echo "$AGENT_SECRET" > "$INSTALL_DIR/config/agent.key"
    chmod 600 "$INSTALL_DIR/config/agent.key"
    echo "  Сгенерирован agent.key"
else
    echo "  agent.key уже существует, пропуск"
fi

# - Основной конфиг
if [[ ! -f "$INSTALL_DIR/config/nullius.yaml" ]]; then
    cat > "$INSTALL_DIR/config/nullius.yaml" <<'YAML'
# - Конфигурация Nullius
server:
  host: 127.0.0.1
  port: 8000

agent:
  interval_sec: 60

database:
  path: /opt/nullius/data/nullius.db

logs:
  dir: /opt/nullius/logs
  level: info

ml:
  models_dir: /opt/nullius/models
  anomaly_threshold: 0.7
YAML
    echo "  Создан nullius.yaml"
else
    echo "  nullius.yaml уже существует, пропуск"
fi

# - Пароль дашборда (basic auth)
DASHBOARD_PASS=""
if [[ ! -f "$INSTALL_DIR/config/.htpasswd" ]]; then
    DASHBOARD_PASS=$(openssl rand -base64 16 | tr -d '=/+' | head -c 16)
    htpasswd -cb "$INSTALL_DIR/config/.htpasswd" admin "$DASHBOARD_PASS"
    chmod 600 "$INSTALL_DIR/config/.htpasswd"
    echo "  Создан .htpasswd (user: admin)"
else
    echo "  .htpasswd уже существует, пропуск"
fi

# - Самоподписанный TLS-сертификат
if [[ ! -f "$INSTALL_DIR/config/tls/cert.pem" ]]; then
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
        -nodes -days 825 -keyout "$INSTALL_DIR/config/tls/key.pem" \
        -out "$INSTALL_DIR/config/tls/cert.pem" \
        -subj "/CN=${DOMAIN:-nullius.local}" \
        2>/dev/null
    chmod 600 "$INSTALL_DIR/config/tls/key.pem"
    echo "  Сгенерирован самоподписанный TLS-сертификат (365 дней)"
else
    echo "  TLS-сертификат уже существует, пропуск"
fi

# ============================================================
# - 8. Права доступа
# ============================================================

log_step "8/10" "Настройка прав..."

chown -R nullius:nullius "$INSTALL_DIR"
# - Агент работает от root (нужен доступ к системным логам)
chown root:root "$INSTALL_DIR/bin/nullius-agent" 2>/dev/null || true

# ============================================================
# - 9. Systemd + nginx
# ============================================================

log_step "9/10" "Настройка сервисов..."

# - Systemd units
cp "$SCRIPT_DIR/nullius-agent.service" /etc/systemd/system/
cp "$SCRIPT_DIR/nullius-api.service" /etc/systemd/system/
systemctl daemon-reload

# - Nginx
cp "$SCRIPT_DIR/nginx-nullius.conf" /etc/nginx/sites-available/nullius
ln -sf /etc/nginx/sites-available/nullius /etc/nginx/sites-enabled/nullius

# - Удаление default-конфига nginx если мешает
if [[ -f /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
fi

nginx -t 2>/dev/null || echo "  ВНИМАНИЕ: nginx config test failed"
systemctl reload nginx 2>/dev/null || systemctl start nginx

# - Nullius CLI
cp "$SCRIPT_DIR/nullius-ctl" /usr/local/bin/nullius-ctl
chmod 755 /usr/local/bin/nullius-ctl

# - Запуск сервисов
systemctl enable nullius-api nullius-agent
systemctl restart nullius-api
systemctl restart nullius-agent

# ============================================================
# - 10. Logrotate
# ============================================================

log_step "10/10" "Настройка logrotate..."

cat > /etc/logrotate.d/nullius <<'LOGROTATE'
/opt/nullius/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 nullius nullius
    postrotate
        systemctl kill -s HUP nullius-api 2>/dev/null || true
    endscript
}
LOGROTATE

# ============================================================
# - Итог
# ============================================================

echo ""
echo "============================================"
echo "  Nullius установлен"
echo "============================================"
echo ""
echo "  Директория:  $INSTALL_DIR"
echo "  Дашборд:     https://$(hostname -I | awk '{print $1}')"
echo "  Логин:       admin"

if [[ -n "$DASHBOARD_PASS" ]]; then
    echo ""
    echo "  ⚠ ВАЖНО: Запишите пароль сейчас, он больше не будет показан!"
    echo "  Пароль:      $DASHBOARD_PASS"
    echo "  (Также сохранён в /opt/nullius/config/.initial_password с правами 600)"
    echo ""
    # - Сохраняем пароль во временный файл
    echo "$DASHBOARD_PASS" > /opt/nullius/config/.initial_password
    chmod 600 /opt/nullius/config/.initial_password
    echo "  Сменить: nullius-ctl set-password"
else
    echo "  Пароль:      (установлен ранее)"
fi

echo ""
echo "  Управление:  nullius-ctl status"
echo "  Логи:        nullius-ctl logs --follow"
echo "  TLS:         nullius-ctl tls --domain example.com"
echo "============================================"
