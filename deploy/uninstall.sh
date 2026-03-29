#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"

log_step() {
    echo "[$1] $2"
}

kill_matching_processes() {
    local pattern="$1"
    pkill -9 -f "$pattern" 2>/dev/null || true
}

remove_port_scan_logging() {
    if command -v iptables >/dev/null 2>&1; then
        iptables -D INPUT -p tcp --syn -m conntrack --ctstate NEW -j NULLIUS_PORTSCAN_LOG 2>/dev/null || true
        iptables -F NULLIUS_PORTSCAN_LOG 2>/dev/null || true
        iptables -X NULLIUS_PORTSCAN_LOG 2>/dev/null || true
    fi
    if command -v ip6tables >/dev/null 2>&1; then
        ip6tables -D INPUT -p tcp --syn -m conntrack --ctstate NEW -j NULLIUS_PORTSCAN_LOG 2>/dev/null || true
        ip6tables -F NULLIUS_PORTSCAN_LOG 2>/dev/null || true
        ip6tables -X NULLIUS_PORTSCAN_LOG 2>/dev/null || true
    fi
}

# Полное удаление Nullius
echo "=== Удаление Nullius ==="

read -p "Удалить Nullius и все данные? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Отменено."
    exit 0
fi

log_step "1/8" "Остановка сервисов..."
systemctl stop nullius-agent nullius-api nullius-backup.timer nullius-backup.service nginx 2>/dev/null || true
systemctl stop nullius-failover-orchestrator.timer nullius-failover-orchestrator.service 2>/dev/null || true
systemctl disable nullius-agent nullius-api nullius-backup.timer nullius-failover-orchestrator.timer 2>/dev/null || true

log_step "2/8" "Принудительное завершение оставшихся процессов..."
kill_matching_processes "/opt/nullius/bin/nullius-agent"
kill_matching_processes "uvicorn asgi:app"
kill_matching_processes "/opt/nullius/server/venv/bin/python -m uvicorn"
kill_matching_processes "/opt/nullius"

log_step "3/8" "Удаление systemd unit-файлов и drop-in конфигов..."
rm -f /etc/systemd/system/nullius-agent.service
rm -f /etc/systemd/system/nullius-api.service
rm -f /etc/systemd/system/nullius-backup.service
rm -f /etc/systemd/system/nullius-backup.timer
rm -f /etc/systemd/system/nullius-failover-orchestrator.service
rm -f /etc/systemd/system/nullius-failover-orchestrator.timer
rm -rf /etc/systemd/system/nullius-api.service.d
rm -rf /etc/systemd/system/nullius-agent.service.d
systemctl daemon-reload
systemctl reset-failed nullius-api nullius-agent nullius-backup.service 2>/dev/null || true
systemctl reset-failed nullius-failover-orchestrator.service 2>/dev/null || true

log_step "4/8" "Удаление nginx-конфига..."
rm -f /etc/nginx/sites-enabled/nullius
rm -f /etc/nginx/sites-available/nullius
rm -f /etc/nginx/conf.d/nullius-limits.conf
rm -f /etc/nginx/snippets/nullius-agent-allowlist.conf
nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

log_step "4.1/8" "Удаление системного hook для port scan..."
remove_port_scan_logging

log_step "5/8" "Удаление logrotate и CLI..."
rm -f /etc/logrotate.d/nullius
rm -f /usr/local/bin/nullius-ctl
rm -f /usr/local/bin/nullius-backup
rm -f /usr/local/bin/nullius-verify-backup
rm -f /usr/local/bin/nullius-restore
rm -f /usr/local/bin/nullius-promote-standby
rm -f /usr/local/bin/nullius-failover-drill
rm -f /usr/local/bin/nullius-failover-orchestrator

log_step "6/8" "Удаление сертификатов и файлов проекта..."
if command -v certbot &>/dev/null; then
    certbot delete --non-interactive 2>/dev/null || true
fi
rm -rf "$INSTALL_DIR"

log_step "7/8" "Удаление системного пользователя nullius..."
userdel nullius 2>/dev/null || true
groupdel nullius 2>/dev/null || true

log_step "8/8" "Финальная очистка..."
find /run/systemd/system -maxdepth 1 -name 'nullius-*' -exec rm -f {} + 2>/dev/null || true
sync

echo "=== Nullius удалён полностью ==="
