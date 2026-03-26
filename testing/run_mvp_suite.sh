#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Nullius MVP Suite ==="
python3 "$ROOT_DIR/testing/smoke/mvp_smoke.py"
(
  cd "$ROOT_DIR/web"
  if [[ ! -d node_modules/@playwright/test ]]; then
    echo "[info] Устанавливаю frontend/e2e зависимости..."
    npm ci --include=dev --silent
  fi
  npx playwright test -c e2e/playwright.config.ts
)
echo "=== MVP suite passed ==="
