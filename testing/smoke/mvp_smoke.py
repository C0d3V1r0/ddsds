#!/usr/bin/env python3
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from pathlib import Path


API_URL = os.environ.get("NULLIUS_API_URL", "http://127.0.0.1:8000").rstrip("/")
DASHBOARD_URL = os.environ.get("NULLIUS_DASHBOARD_URL", "https://127.0.0.1").rstrip("/")
DASHBOARD_USER = os.environ.get("NULLIUS_DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.environ.get("NULLIUS_DASHBOARD_PASSWORD", "").strip()
SKIP_SYSTEMD = os.environ.get("NULLIUS_SKIP_SYSTEMD", "") == "1"

PASSWORD_FILE = Path("/opt/nullius/config/.initial_password")
SSL_CONTEXT = ssl._create_unverified_context()


def load_password() -> str:
    if DASHBOARD_PASSWORD:
        return DASHBOARD_PASSWORD
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text().strip()
    return ""


def pass_msg(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def request_json(path: str, method: str = "GET", body: dict | None = None) -> object:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        fail(f"{method} {path} returned HTTP {exc.code}")
    except Exception as exc:  # pragma: no cover - runtime diagnostics
        fail(f"{method} {path} failed: {exc}")
    raise AssertionError("unreachable")


def request_dashboard() -> str:
    password = load_password()
    if not password:
        fail("Dashboard password not found in env or /opt/nullius/config/.initial_password")
    token = b64encode(f"{DASHBOARD_USER}:{password}".encode()).decode()
    req = urllib.request.Request(
        DASHBOARD_URL + "/",
        headers={"Authorization": f"Basic {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5, context=SSL_CONTEXT) as resp:
            return resp.read().decode()
    except Exception as exc:
        fail(f"Dashboard request failed: {exc}")
    raise AssertionError("unreachable")


def check_systemd() -> None:
    if SKIP_SYSTEMD:
        print("[WARN] systemd checks skipped by NULLIUS_SKIP_SYSTEMD=1")
        return
    for service in ("nullius-api", "nullius-agent", "nginx"):
        result = subprocess.run(
            ["systemctl", "is-active", service],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            fail(f"Service {service} is not active")
        pass_msg(f"Service {service} is active")


def wait_for(predicate, timeout: float, interval: float, description: str):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    fail(description)


def check_health() -> None:
    health = request_json("/api/health")
    if not isinstance(health, dict):
        fail("/api/health did not return an object")
    if health.get("status") != "ok":
        fail("API status is not ok")
    if health.get("db") != "ok":
        fail("Database status is not ok")
    if health.get("agent") != "connected":
        fail("Agent is not connected")
    pass_msg("API health is ok and agent is connected")


def check_metrics() -> None:
    metrics = request_json("/api/metrics")
    if not isinstance(metrics, dict):
        fail("/api/metrics did not return an object")
    for key in ("cpu_total", "ram_used", "ram_total", "network_rx", "network_tx"):
        if key not in metrics:
            fail(f"/api/metrics missing key: {key}")
    pass_msg("Metrics endpoint returns current metrics")


def check_lists() -> None:
    for path, label in (
        ("/api/services", "services"),
        ("/api/processes", "processes"),
        ("/api/logs?limit=20", "logs"),
        ("/api/security/events?limit=20", "security events"),
        ("/api/security/blocked", "blocked IP list"),
    ):
        data = request_json(path)
        if not isinstance(data, list):
            fail(f"{path} did not return a list")
        pass_msg(f"{label.capitalize()} endpoint is readable")


def check_process_collection() -> None:
    proc = subprocess.Popen(["sleep", "45"])
    try:
        def has_sleep():
            processes = request_json("/api/processes")
            if not isinstance(processes, list):
                return False
            return any(
                isinstance(item, dict)
                and item.get("pid") == proc.pid
                and str(item.get("name", "")).startswith("sleep")
                for item in processes
            )

        wait_for(has_sleep, timeout=20, interval=2, description="Temporary process was not visible via /api/processes")
        pass_msg("Temporary process is visible in process snapshot")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def check_log_collection() -> None:
    marker = f"nullius-smoke-{int(time.time())}"
    password = load_password()
    if not password:
        fail("Dashboard password not found for log smoke check")

    req = urllib.request.Request(
        f"{DASHBOARD_URL}/{marker}",
        headers={
            "Authorization": f"Basic {b64encode(f'{DASHBOARD_USER}:{password}'.encode()).decode()}",
            "User-Agent": f"nullius-smoke/{marker}",
        },
        method="GET",
    )
    try:
        urllib.request.urlopen(req, timeout=5, context=SSL_CONTEXT)
    except urllib.error.HTTPError:
        # - 404 тоже подходит: nginx access log всё равно должен содержать запрос
        pass
    except Exception as exc:
        fail(f"Failed to generate nginx access log entry: {exc}")

    def has_marker():
        logs = request_json("/api/logs?limit=200")
        if not isinstance(logs, list):
            return False
        return any(
            isinstance(item, dict)
            and marker in str(item.get("line", ""))
            for item in logs
        )

    wait_for(has_marker, timeout=20, interval=2, description="Generated nginx access log entry was not visible via /api/logs")
    pass_msg("Generated nginx access log entry is visible in logs")


def check_block_unblock() -> None:
    ip = "203.0.113.250"
    reason = f"mvp-smoke-{int(time.time())}"
    request_json("/api/security/block", method="POST", body={"ip": ip, "reason": reason, "duration": 120})

    def is_blocked():
        blocked = request_json("/api/security/blocked")
        if not isinstance(blocked, list):
            return False
        return any(isinstance(item, dict) and item.get("ip") == ip for item in blocked)

    wait_for(is_blocked, timeout=10, interval=1, description="Blocked IP was not visible via /api/security/blocked")
    pass_msg("Manual block IP API works")

    request_json("/api/security/unblock", method="POST", body={"ip": ip})

    def is_unblocked():
        blocked = request_json("/api/security/blocked")
        if not isinstance(blocked, list):
            return False
        return not any(isinstance(item, dict) and item.get("ip") == ip for item in blocked)

    wait_for(is_unblocked, timeout=10, interval=1, description="Blocked IP was not removed after unblock")
    pass_msg("Manual unblock IP API works")


def check_dashboard() -> None:
    html = request_dashboard()
    if "NULLIUS" not in html:
        fail("Dashboard HTML does not contain NULLIUS brand")
    pass_msg("Dashboard HTML is reachable via HTTPS")


def main() -> None:
    print("=== Nullius MVP Smoke ===")
    check_systemd()
    check_health()
    check_metrics()
    check_lists()
    check_process_collection()
    check_log_collection()
    check_block_unblock()
    check_dashboard()
    print("=== Smoke passed ===")


if __name__ == "__main__":
    main()
