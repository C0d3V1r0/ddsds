#!/usr/bin/env python3
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request


API_URL = os.environ.get("NULLIUS_API_URL", "http://127.0.0.1:8000").rstrip("/")
SCAN_TARGET_HOST = os.environ.get("NULLIUS_SCAN_TARGET_HOST", "").strip()
SCAN_PORTS = tuple(
    int(item)
    for item in os.environ.get("NULLIUS_SCAN_PORTS", "22,25,53,80,110,139,143,443,445,3306,5432,6379").split(",")
    if item.strip()
)
WAIT_TIMEOUT = int(os.environ.get("NULLIUS_SCAN_WAIT_TIMEOUT", "30"))
CONNECT_TIMEOUT = float(os.environ.get("NULLIUS_SCAN_CONNECT_TIMEOUT", "0.25"))


def pass_msg(message: str) -> None:
    print(f"[PASS] {message}")


def warn_msg(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def request_json(path: str) -> object:
    req = urllib.request.Request(f"{API_URL}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        fail(f"GET {path} returned HTTP {exc.code}")
    except Exception as exc:
        fail(f"GET {path} failed: {exc}")
    raise AssertionError("unreachable")


def find_recent_port_scan(started_at: int) -> dict | None:
    events = request_json("/api/security/events?event_type=port_scan&limit=20")
    if not isinstance(events, list):
        return None
    for item in events:
        if not isinstance(item, dict):
            continue
        if int(item.get("timestamp", 0) or 0) >= started_at:
            return item
    return None


def run_connect_scan(target_host: str) -> None:
    for port in SCAN_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        try:
            sock.connect((target_host, port))
        except OSError:
            pass
        finally:
            sock.close()


def main() -> None:
    if not SCAN_TARGET_HOST:
        warn_msg("NULLIUS_SCAN_TARGET_HOST не задан, runtime port-scan smoke пропущен")
        return

    print("=== Nullius Port Scan Smoke ===")
    started_at = int(time.time())
    run_connect_scan(SCAN_TARGET_HOST)

    deadline = time.time() + WAIT_TIMEOUT
    while time.time() < deadline:
        event = find_recent_port_scan(started_at)
        if event:
            pass_msg(
                f"Port scan detected from {event.get('source_ip') or 'unknown source'} "
                f"with severity {event.get('severity', 'unknown')}"
            )
            print("=== Port scan smoke passed ===")
            return
        time.sleep(2)

    fail("Port scan event was not detected within timeout")


if __name__ == "__main__":
    main()
