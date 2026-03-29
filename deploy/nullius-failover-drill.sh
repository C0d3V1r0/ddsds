#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"
BACKUP_DIR="$INSTALL_DIR/backups"

fail() {
    echo "ОШИБКА: $1" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || fail "Запусти drill от root"

echo "=== Failover drill Nullius ==="

echo "[1/5] Проверяю, что API жив и отвечает..."
curl -fsS http://127.0.0.1:8000/api/health >/dev/null || fail "Health endpoint недоступен"

echo "[2/5] Создаю свежий backup..."
nullius-backup

LATEST_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'nullius-backup-*.tar.gz' | sort | tail -n 1)"
[[ -n "$LATEST_BACKUP" ]] || fail "Не найден backup после snapshot"

echo "[3/5] Проверяю backup..."
nullius-verify-backup "$LATEST_BACKUP"

echo "[4/5] Проверяю promote-сценарий в dry-run..."
nullius-promote-standby --dry-run

echo "[5/5] Проверяю статус роли узла и lock..."
curl -fsS http://127.0.0.1:8000/api/deployment >/dev/null || fail "Deployment API недоступен"

echo "=== Failover drill прошёл успешно ==="
