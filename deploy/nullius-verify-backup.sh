#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"
BACKUP_DIR="$INSTALL_DIR/backups"
VERIFY_ROOT="$(mktemp -d)"

cleanup() {
    rm -rf "$VERIFY_ROOT"
}
trap cleanup EXIT

fail() {
    echo "ОШИБКА: $1" >&2
    exit 1
}

ARCHIVE_PATH="${1:-}"
if [[ -z "$ARCHIVE_PATH" ]]; then
    ARCHIVE_PATH="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'nullius-backup-*.tar.gz' | sort | tail -n 1)"
fi

[[ -n "$ARCHIVE_PATH" ]] || fail "Не найден архив для проверки"
[[ -f "$ARCHIVE_PATH" ]] || fail "Архив не существует: $ARCHIVE_PATH"

echo "=== Проверка backup Nullius ==="
echo "Архив: $ARCHIVE_PATH"

tar xzf "$ARCHIVE_PATH" -C "$VERIFY_ROOT"

if [[ -f "$VERIFY_ROOT/nullius.db" ]]; then
    echo "[1/3] Проверяю SQLite..."
    sqlite3 "$VERIFY_ROOT/nullius.db" "PRAGMA integrity_check;" | grep -qx "ok" \
        || fail "SQLite backup не проходит integrity_check"

    required_tables=(metrics security_events blocked_ips response_audit)
    for table in "${required_tables[@]}"; do
        sqlite3 "$VERIFY_ROOT/nullius.db" "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" \
            | grep -qx "$table" || fail "В backup отсутствует таблица $table"
    done
else
    echo "[1/3] SQLite backup отсутствует, пропускаю"
fi

echo "[2/3] Проверяю конфиг..."
[[ -d "$VERIFY_ROOT/config" ]] || fail "В backup отсутствует директория config"
[[ -f "$VERIFY_ROOT/config/nullius.yaml" ]] || fail "В backup отсутствует nullius.yaml"
[[ -f "$VERIFY_ROOT/config/agent.key" ]] || fail "В backup отсутствует agent.key"

echo "[3/3] Проверяю состав архива..."
find "$VERIFY_ROOT" -maxdepth 2 -type f | sort

echo "=== Backup Nullius корректен ==="
