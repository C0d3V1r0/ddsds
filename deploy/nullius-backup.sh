#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"
BACKUP_DIR="$INSTALL_DIR/backups"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP_DIR="$(mktemp -d)"
ARCHIVE_PATH="$BACKUP_DIR/nullius-backup-${TIMESTAMP}.tar.gz"
RETENTION_DAYS="${NULLIUS_BACKUP_RETENTION_DAYS:-7}"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$BACKUP_DIR"

# Сохраняем консистентную копию SQLite через встроенный backup-механизм.
if [[ -f "$INSTALL_DIR/data/nullius.db" ]]; then
    sqlite3 "$INSTALL_DIR/data/nullius.db" ".backup '$TMP_DIR/nullius.db'"
fi

mkdir -p "$TMP_DIR/config"
if [[ -d "$INSTALL_DIR/config" ]]; then
    cp -a "$INSTALL_DIR/config/." "$TMP_DIR/config/"
fi

tar czf "$ARCHIVE_PATH" -C "$TMP_DIR" .
chmod 600 "$ARCHIVE_PATH"

find "$BACKUP_DIR" -type f -name 'nullius-backup-*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

echo "Nullius backup created: $ARCHIVE_PATH"
