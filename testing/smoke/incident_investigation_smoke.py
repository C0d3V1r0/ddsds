#!/usr/bin/env python3
"""Smoke-проверка investigation layer на живом стенде."""

from __future__ import annotations

import os
import sys
from typing import Any

import requests


API_URL = os.getenv("NULLIUS_API_URL", "http://127.0.0.1:8000").rstrip("/")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def get_json(path: str) -> Any:
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def main() -> None:
    print("=== Nullius Incident Investigation Smoke ===")

    health = get_json("/api/health")
    if health.get("status") != "ok":
        fail("API health is not ok")
    ok("API health is ok")

    incidents = get_json("/api/security/incidents?limit=20")
    if not incidents:
        warn("Инцидентов пока нет. Detail API не с чем валидировать на этом стенде.")
        print("=== Incident Investigation Smoke skipped ===")
        return

    incident_id = incidents[0]["id"]
    detail = get_json(f"/api/security/incidents/{incident_id}")

    required_keys = {
        "incident",
        "related_events",
        "blocked_ip",
        "audit_entries",
        "notes",
        "progression",
        "evidence_summary",
        "resolution_summary",
    }
    missing = sorted(required_keys - set(detail.keys()))
    if missing:
        fail(f"Incident detail is missing keys: {', '.join(missing)}")

    if detail["incident"]["id"] != incident_id:
        fail("Incident detail returned a mismatched incident id")
    ok("Incident detail returns the expected incident payload")

    if not isinstance(detail["related_events"], list):
        fail("related_events must be a list")
    if not isinstance(detail["progression"], list):
        fail("progression must be a list")
    if not isinstance(detail["evidence_summary"], list):
        fail("evidence_summary must be a list")
    if not isinstance(detail["resolution_summary"], dict):
        fail("resolution_summary must be a dict")
    ok("Incident detail shape looks correct")

    resolution = detail["resolution_summary"]
    if "state" not in resolution or "headline" not in resolution:
        fail("resolution_summary must include state and headline")
    ok("Resolution summary includes state and headline")

    print(f"[INFO] validated incident: {incident_id}")
    print("=== Incident Investigation Smoke passed ===")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        fail(f"HTTP error: {exc}")
