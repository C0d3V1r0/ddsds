#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"
CONFIG_PATH="${NULLIUS_CONFIG:-$INSTALL_DIR/config/nullius.yaml}"
STATE_DIR="$INSTALL_DIR/data"
LOG_PREFIX="Nullius failover orchestrator"

log() {
    echo "[$LOG_PREFIX] $1"
}

fail() {
    echo "[$LOG_PREFIX] ERROR: $1" >&2
    exit 1
}

[[ -f "$CONFIG_PATH" ]] || fail "Не найден конфиг: $CONFIG_PATH"

readarray -t CFG < <(python3 - <<'PY' "$CONFIG_PATH"
from pathlib import Path
import sys
import yaml

config_path = Path(sys.argv[1])
data = yaml.safe_load(config_path.read_text()) or {}
deployment = data.get("deployment", {}) or {}
failover = data.get("failover", {}) or {}

def emit(value):
    print("" if value is None else str(value))

emit(deployment.get("role", "primary"))
emit(deployment.get("primary_lock_path", "/opt/nullius/data/primary.lock"))
emit(failover.get("enabled", False))
emit(failover.get("primary_api_url", ""))
emit(failover.get("failure_threshold", 3))
emit(failover.get("cooloff_seconds", 600))
emit(failover.get("state_file", "/opt/nullius/data/failover-state.json"))
PY
)

ROLE="${CFG[0]}"
LOCK_PATH="${CFG[1]}"
FAILOVER_ENABLED="${CFG[2]}"
PRIMARY_API_URL="${CFG[3]}"
FAILURE_THRESHOLD="${CFG[4]}"
COOLOFF_SECONDS="${CFG[5]}"
STATE_FILE="${CFG[6]}"

if [[ "$ROLE" != "standby" ]]; then
    log "узел не standby, orchestration пропущен"
    exit 0
fi

if [[ "$FAILOVER_ENABLED" != "True" && "$FAILOVER_ENABLED" != "true" ]]; then
    log "failover orchestration выключен в конфиге"
    exit 0
fi

[[ -n "$PRIMARY_API_URL" ]] || fail "Для failover orchestration не задан failover.primary_api_url"

mkdir -p "$STATE_DIR"

python3 - <<'PY' "$PRIMARY_API_URL" "$LOCK_PATH" "$FAILURE_THRESHOLD" "$COOLOFF_SECONDS" "$STATE_FILE"
from pathlib import Path
import fcntl
import json
import subprocess
import sys
import time
from urllib import request, error

primary_api_url = sys.argv[1].rstrip("/")
lock_path = Path(sys.argv[2])
failure_threshold = max(1, int(sys.argv[3]))
cooloff_seconds = max(60, int(sys.argv[4]))
state_file = Path(sys.argv[5])
now = int(time.time())

if state_file.exists():
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        state = {}
else:
    state = {}

state.setdefault("consecutive_failures", 0)
state.setdefault("last_failure_at", 0)
state.setdefault("last_success_at", 0)
state.setdefault("last_promote_attempt_at", 0)

health_url = f"{primary_api_url}/api/health"
healthy = False
try:
    with request.urlopen(health_url, timeout=5) as resp:
        if resp.status == 200:
            payload = json.loads(resp.read().decode("utf-8"))
            healthy = payload.get("status") == "ok"
except (error.URLError, TimeoutError, json.JSONDecodeError):
    healthy = False

if healthy:
    state["consecutive_failures"] = 0
    state["last_success_at"] = now
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("HEALTHY")
    raise SystemExit(0)

state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
state["last_failure_at"] = now
state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

if state["consecutive_failures"] < failure_threshold:
    print(f"WAIT:{state['consecutive_failures']}")
    raise SystemExit(0)

if now - int(state.get("last_promote_attempt_at", 0)) < cooloff_seconds:
    print("COOLOFF")
    raise SystemExit(0)

lock_path.parent.mkdir(parents=True, exist_ok=True)
fd = open(lock_path, "a+", encoding="utf-8")
try:
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("LOCKED")
        raise SystemExit(0)
    else:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
finally:
    fd.close()

state["last_promote_attempt_at"] = now
state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
subprocess.run(["/usr/local/bin/nullius-promote-standby"], check=True)
print("PROMOTED")
PY
