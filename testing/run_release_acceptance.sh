#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

if [[ "${1:-}" != "--destructive" ]]; then
  cat <<'EOF'
Использование:
  ./testing/run_release_acceptance.sh --destructive

Что делает скрипт:
  1. Собирает релиз
  2. Полностью переустанавливает Nullius через uninstall/install
  3. Проверяет /api/health
  4. Запускает smoke и полный MVP suite

Внимание: сценарий разрушительный для текущей локальной установки.
EOF
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Запусти acceptance-скрипт от root." >&2
  exit 1
fi

echo "=== Nullius Release Acceptance ==="
"$ROOT_DIR/deploy/build.sh"

cd "$DIST_DIR"
./uninstall.sh <<<"y"
./install.sh

echo "[health] Проверяю runtime..."
curl --fail --silent http://127.0.0.1:8000/api/health
echo

echo "[backup] Проверяю backup/verify контур..."
/usr/local/bin/nullius-backup
/usr/local/bin/nullius-verify-backup

cd "$ROOT_DIR"
python3 "$ROOT_DIR/testing/smoke/mvp_smoke.py"
"$ROOT_DIR/testing/run_mvp_suite.sh"

echo "=== Release acceptance passed ==="
