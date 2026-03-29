#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Nullius Security Validation Suite ==="
python3 "$ROOT_DIR/testing/smoke/mvp_smoke.py"
python3 "$ROOT_DIR/testing/smoke/incident_investigation_smoke.py"

if [[ -n "${NULLIUS_SCAN_TARGET_HOST:-}" ]]; then
  python3 "$ROOT_DIR/testing/smoke/port_scan_smoke.py"
else
  echo "[info] NULLIUS_SCAN_TARGET_HOST не задан, runtime port-scan smoke пропущен."
fi

echo "=== Security Validation Suite passed ==="
