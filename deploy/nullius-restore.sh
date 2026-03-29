#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"
BACKUP_DIR="$INSTALL_DIR/backups"
RESTORE_ROOT="$(mktemp -d)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SAFETY_DIR="$BACKUP_DIR/pre-restore-$STAMP"

cleanup() {
    rm -rf "$RESTORE_ROOT"
}
trap cleanup EXIT

fail() {
    echo "ОШИБКА: $1" >&2
    exit 1
}

require_root() {
    [[ $EUID -eq 0 ]] || fail "Запусти восстановление от root"
}

ARCHIVE_PATH="${1:-}"
if [[ -z "$ARCHIVE_PATH" ]]; then
    ARCHIVE_PATH="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'nullius-backup-*.tar.gz' | sort | tail -n 1)"
fi

require_root
[[ -n "$ARCHIVE_PATH" ]] || fail "Не найден backup для восстановления"
[[ -f "$ARCHIVE_PATH" ]] || fail "Архив не существует: $ARCHIVE_PATH"

echo "=== Восстановление Nullius ==="
echo "Архив: $ARCHIVE_PATH"

/usr/local/bin/nullius-verify-backup "$ARCHIVE_PATH"
tar xzf "$ARCHIVE_PATH" -C "$RESTORE_ROOT"

[[ -f "$RESTORE_ROOT/nullius.db" || -d "$RESTORE_ROOT/config" ]] || fail "В архиве нет данных для восстановления"

echo "[1/5] Останавливаю сервисы..."
systemctl stop nullius-api nullius-agent nullius-backup.timer 2>/dev/null || true

echo "[2/5] Делаю safety snapshot перед restore..."
mkdir -p "$SAFETY_DIR"
if [[ -f "$INSTALL_DIR/data/nullius.db" ]]; then
    sqlite3 "$INSTALL_DIR/data/nullius.db" ".backup '$SAFETY_DIR/nullius.db'"
fi
if [[ -d "$INSTALL_DIR/config" ]]; then
    mkdir -p "$SAFETY_DIR/config"
    cp -a "$INSTALL_DIR/config/." "$SAFETY_DIR/config/"
fi

echo "[3/5] Восстанавливаю БД..."
if [[ -f "$RESTORE_ROOT/nullius.db" ]]; then
    mkdir -p "$INSTALL_DIR/data"
    install -o nullius -g nullius -m 600 "$RESTORE_ROOT/nullius.db" "$INSTALL_DIR/data/nullius.db"
fi

echo "[4/5] Восстанавливаю конфиг..."
if [[ -d "$RESTORE_ROOT/config" ]]; then
    mkdir -p "$INSTALL_DIR/config"
    cp -a "$RESTORE_ROOT/config/." "$INSTALL_DIR/config/"
    chown -R nullius:nullius "$INSTALL_DIR/config"
    find "$INSTALL_DIR/config" -type f -name '*.key' -exec chmod 600 {} +
    find "$INSTALL_DIR/config" -type f ! -name '*.key' -exec chmod 640 {} +
fi

echo "[5/5] Поднимаю сервисы и проверяю health..."
systemctl start nullius-api nullius-agent nullius-backup.timer
sleep 2
curl --fail --silent http://127.0.0.1:8000/api/health >/dev/null \
    || fail "После restore health-check не прошёл"

echo "Safety snapshot сохранён в: $SAFETY_DIR"
echo "=== Восстановление завершено ==="
