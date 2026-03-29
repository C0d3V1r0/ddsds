#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"
CONFIG_PATH="${NULLIUS_CONFIG:-$INSTALL_DIR/config/nullius.yaml}"
DRY_RUN=0
FORCE=0

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --force) FORCE=1 ;;
        *) ;;
    esac
done

fail() {
    echo "ОШИБКА: $1" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || fail "Запустите от root"
[[ -f "$CONFIG_PATH" ]] || fail "Не найден конфиг: $CONFIG_PATH"

LOCK_PATH="$(python3 - <<'PY' "$CONFIG_PATH"
from pathlib import Path
import sys
import yaml

config_path = Path(sys.argv[1])
data = yaml.safe_load(config_path.read_text()) or {}
deployment = data.get("deployment", {}) or {}
print(str(deployment.get("primary_lock_path", "/opt/nullius/data/primary.lock")))
PY
)"

if ! grep -qE '^[[:space:]]*role:[[:space:]]*standby[[:space:]]*$' "$CONFIG_PATH"; then
    echo "Nullius уже не в standby-режиме или роль не указана явно."
fi

LOCK_STATUS="$(python3 - <<'PY' "$LOCK_PATH"
from pathlib import Path
import fcntl
import json
import sys

lock_path = Path(sys.argv[1])
lock_path.parent.mkdir(parents=True, exist_ok=True)
fd = open(lock_path, "a+", encoding="utf-8")
try:
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        locked = True
    else:
        locked = False
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
finally:
    fd.close()

payload = {}
if lock_path.exists():
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8").strip() or "{}")
    except Exception:
        payload = {}

print(json.dumps({
    "locked": locked,
    "owner": str(payload.get("node_name", "") or ""),
    "pid": int(payload.get("pid", 0) or 0),
}, ensure_ascii=False))
PY
)"

LOCK_HELD="$(python3 - <<'PY' "$LOCK_STATUS"
import json, sys
print("1" if json.loads(sys.argv[1]).get("locked") else "0")
PY
)"

if [[ "$LOCK_HELD" == "1" && "$FORCE" -ne 1 ]]; then
    OWNER_HINT="$(python3 - <<'PY' "$LOCK_STATUS"
import json, sys
payload = json.loads(sys.argv[1])
owner = payload.get("owner") or "unknown"
pid = int(payload.get("pid", 0) or 0)
suffix = f" (PID {pid})" if pid > 0 else ""
print(f"{owner}{suffix}")
PY
)"
    fail "Primary lock уже удерживается другим узлом: $OWNER_HINT. Если исходный primary гарантированно изолирован, повтори promote с --force."
fi

echo "[1/5] Создаю safety backup перед promote..."
nullius-backup

LATEST_BACKUP="$(find "$INSTALL_DIR/backups" -maxdepth 1 -type f -name 'nullius-backup-*.tar.gz' | sort | tail -n 1)"
[[ -n "$LATEST_BACKUP" ]] || fail "Не найден свежий backup после snapshot"

echo "[2/5] Проверяю backup перед promote..."
nullius-verify-backup "$LATEST_BACKUP"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[3/5] Dry-run: проверка promote завершена, конфиг не меняю."
    exit 0
fi

echo "[3/5] Перевожу узел в primary..."
python3 - <<'PY' "$CONFIG_PATH"
from pathlib import Path
import sys
import yaml

config_path = Path(sys.argv[1])
data = yaml.safe_load(config_path.read_text()) or {}
deployment = data.setdefault("deployment", {})
deployment["role"] = "primary"
config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
PY

echo "[4/5] Перезапускаю сервисы..."
systemctl restart nullius-api
systemctl restart nullius-agent

echo "[5/5] Проверяю health..."
curl -fsS http://127.0.0.1:8000/api/health >/dev/null || fail "Health check не прошёл после promote"

echo "Standby-узел переведён в primary."
