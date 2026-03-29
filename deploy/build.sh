#!/usr/bin/env bash
set -euo pipefail

# Скрипт сборки Nullius: Go agent + React frontend + Python server
VERSION="${1:-1.0.1-beta}"
BUILD_DIR="dist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "=== Сборка Nullius v${VERSION} ==="

# 1. Сборка Go агента для Linux amd64 + arm64
echo "[1/4] Go agent..."
cd "$PROJECT_DIR/agent"
GOOS=linux GOARCH=amd64 go build -ldflags "-s -w" -o "$PROJECT_DIR/$BUILD_DIR/nullius-agent-amd64" .
GOOS=linux GOARCH=arm64 go build -ldflags "-s -w" -o "$PROJECT_DIR/$BUILD_DIR/nullius-agent-arm64" .

# 2. Сборка React frontend
echo "[2/4] Frontend..."
cd "$PROJECT_DIR/web"
npm ci --include=dev --silent

log_audit() { echo "  ВНИМАНИЕ: Найдены уязвимости в npm-зависимостях"; }
echo "Проверяю зависимости фронтенда..."
npm audit --audit-level=high 2>&1 || log_audit

npm run build
mkdir -p "$PROJECT_DIR/$BUILD_DIR/web"
cp -r dist/. "$PROJECT_DIR/$BUILD_DIR/web/"

# 3. Упаковка Python server (без venv, тестов, кэша)
echo "[3/4] Server..."
cd "$PROJECT_DIR"
tar czf "$BUILD_DIR/server.tar.gz" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='venv' \
  --exclude='tests' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  server/

# 4. Копирование deploy-файлов
echo "[4/4] Deploy files..."
cp deploy/install.sh "$BUILD_DIR/"
cp deploy/nullius-ctl "$BUILD_DIR/"
cp deploy/nullius-agent.service "$BUILD_DIR/"
cp deploy/nullius-api.service "$BUILD_DIR/"
cp deploy/nullius-backup.sh "$BUILD_DIR/"
cp deploy/nullius-verify-backup.sh "$BUILD_DIR/"
cp deploy/nullius-restore.sh "$BUILD_DIR/"
cp deploy/nullius-promote-standby.sh "$BUILD_DIR/"
cp deploy/nullius-failover-drill.sh "$BUILD_DIR/"
cp deploy/nullius-failover-orchestrator.sh "$BUILD_DIR/"
cp deploy/nullius-backup.service "$BUILD_DIR/"
cp deploy/nullius-backup.timer "$BUILD_DIR/"
cp deploy/nullius-failover-orchestrator.service "$BUILD_DIR/"
cp deploy/nullius-failover-orchestrator.timer "$BUILD_DIR/"
cp deploy/nginx-nullius.conf "$BUILD_DIR/"
cp deploy/nginx-nullius-limits.conf "$BUILD_DIR/"
cp deploy/nginx-agent-allowlist.conf "$BUILD_DIR/"
cp deploy/uninstall.sh "$BUILD_DIR/"

# Генерация контрольных сумм
echo "Генерирую контрольные суммы..."
(cd "$PROJECT_DIR/$BUILD_DIR" && sha256sum nullius-agent-* server.tar.gz > checksums.sha256)

echo "=== Сборка завершена: ${BUILD_DIR}/ ==="
ls -lh "$BUILD_DIR/"
