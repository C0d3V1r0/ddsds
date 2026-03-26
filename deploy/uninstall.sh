#!/usr/bin/env bash
set -euo pipefail

# - Полное удаление Nullius
echo "=== Удаление Nullius ==="

read -p "Удалить Nullius и все данные? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Отменено."
    exit 0
fi

echo "[1/5] Остановка сервисов..."
systemctl stop nullius-agent nullius-api 2>/dev/null || true
systemctl disable nullius-agent nullius-api 2>/dev/null || true

echo "[2/5] Удаление systemd unit-файлов..."
rm -f /etc/systemd/system/nullius-agent.service
rm -f /etc/systemd/system/nullius-api.service
systemctl daemon-reload

echo "[3/6] Удаление nginx-конфига..."
rm -f /etc/nginx/sites-enabled/nullius
rm -f /etc/nginx/sites-available/nullius
nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

echo "[4/6] Удаление Let's Encrypt сертификатов..."
# - Удаление Let's Encrypt сертификатов
if command -v certbot &>/dev/null; then
    certbot delete --non-interactive 2>/dev/null || true
fi

echo "[5/6] Удаление logrotate..."
rm -f /etc/logrotate.d/nullius

echo "[6/6] Удаление файлов..."
rm -rf /opt/nullius
rm -f /usr/local/bin/nullius-ctl

# - Пользователя не удаляем — может использоваться другими сервисами
echo "=== Nullius удалён ==="
echo "Системный пользователь 'nullius' оставлен. Удалите вручную: userdel nullius"
