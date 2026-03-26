#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Nullius MVP Suite ==="
python3 "$ROOT_DIR/testing/smoke/mvp_smoke.py"
(
  cd "$ROOT_DIR/web"
  npx playwright test -c ../testing/e2e/playwright.config.ts
)
echo "=== MVP suite passed ==="
