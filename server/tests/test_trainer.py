# Тесты тренера ML-моделей: очистка baseline от шумных интервалов и статус причин
import time

import aiosqlite
import pytest

from db import init_db
from ml.trainer import (
    MAX_EVENTS_CLEAN_BASELINE,
    MIN_TRAINING_SAMPLES,
    get_anomaly_status,
    train_anomaly_from_db,
)


async def _seed_metrics(db_path: str, start_ts: int, count: int, step_seconds: int = 60) -> None:
    async with aiosqlite.connect(db_path) as conn:
        for index in range(count):
            ts = start_ts + index * step_seconds
            await conn.execute(
                """
                INSERT INTO metrics (
                    timestamp, cpu_total, cpu_cores, ram_used, ram_total, disk,
                    network_rx, network_tx, load_avg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    12.5 + (index % 7),
                    "[0,1]",
                    512_000_000 + index * 1024,
                    2_048_000_000,
                    "[]",
                    1_000 + index,
                    2_000 + index,
                    "[0.2,0.3,0.4]",
                ),
            )
        await conn.commit()


async def _seed_security_events(db_path: str, timestamps: list[int]) -> None:
    async with aiosqlite.connect(db_path) as conn:
        for ts in timestamps:
            await conn.execute(
                """
                INSERT INTO security_events (
                    timestamp, type, severity, source_ip, description, raw_log, action_taken, resolved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    "ssh_brute_force",
                    "high",
                    "203.0.113.10",
                    "test-event",
                    "raw",
                    "logged",
                    0,
                ),
            )
        await conn.commit()


@pytest.mark.asyncio
async def test_trainer_uses_filtered_baseline_when_window_is_noisy(tmp_path):
    db_path = str(tmp_path / "trainer-filtered.db")
    await init_db(db_path)

    now = int(time.time()) - 4 * 3600
    await _seed_metrics(db_path, now, 180, step_seconds=60)
    noisy_timestamps = [now + index * 600 for index in range(MAX_EVENTS_CLEAN_BASELINE + 15)]
    await _seed_security_events(db_path, noisy_timestamps)

    trained = await train_anomaly_from_db(db_path, hours=24)

    assert trained is True
    status = get_anomaly_status()
    assert status["status"] == "running"
    assert status["reason_code"] == "ready_filtered_baseline"
    assert status["event_count"] > MAX_EVENTS_CLEAN_BASELINE
    assert status["filtered_samples_count"] >= MIN_TRAINING_SAMPLES
    assert status["filtered_samples_count"] < status["samples_count"]
    assert status["filter_window_seconds"] > 0
    assert status["weighted_event_pressure"] > status["event_count"]
    assert status["excluded_windows_count"] > 0


@pytest.mark.asyncio
async def test_trainer_marks_insufficient_clean_data_when_noise_eats_window(tmp_path):
    db_path = str(tmp_path / "trainer-insufficient-clean.db")
    await init_db(db_path)

    now = int(time.time()) - 2 * 3600
    await _seed_metrics(db_path, now, 120, step_seconds=60)
    # Частые события размазывают почти всё окно, поэтому сырья достаточно,
    # но чистого baseline после вырезания шумных участков уже не хватает.
    noisy_timestamps = [now + index * 120 for index in range(MAX_EVENTS_CLEAN_BASELINE + 45)]
    await _seed_security_events(db_path, noisy_timestamps)

    trained = await train_anomaly_from_db(db_path, hours=24)

    assert trained is False
    status = get_anomaly_status()
    assert status["status"] == "insufficient_data"
    assert status["reason_code"] == "insufficient_clean_data"
    assert status["samples_count"] >= MIN_TRAINING_SAMPLES
    assert 0 < status["filtered_samples_count"] < MIN_TRAINING_SAMPLES
    assert status["filter_window_seconds"] > 0
    assert status["dataset_noise_label"] == "noisy"


@pytest.mark.asyncio
async def test_trainer_tracks_maintenance_windows_and_host_profile(tmp_path):
    db_path = str(tmp_path / "trainer-maintenance.db")
    await init_db(db_path)

    now = int(time.time()) - 4 * 3600
    await _seed_metrics(db_path, now, 220, step_seconds=60)

    async with aiosqlite.connect(db_path) as conn:
        for ts in (now + 900, now + 1_800, now + 2_700):
            await conn.execute(
                "INSERT INTO agent_commands (timestamp, command, params, result, error) VALUES (?, ?, ?, ?, ?)",
                (ts, "restart_service", "{}", "success", ""),
            )
        await conn.commit()

    trained = await train_anomaly_from_db(
        db_path,
        hours=24,
        min_samples=100,
        max_clean_events=10,
        base_buffer_seconds=300,
        host_profile="database",
        maintenance_window_seconds=300,
        maintenance_commands=("restart_service",),
    )

    assert trained is True
    status = get_anomaly_status()
    assert status["host_profile"] == "database"
    assert status["maintenance_event_count"] == 3
    assert status["maintenance_window_seconds"] == 300
    assert status["required_samples"] > 100
    assert status["excluded_windows_count"] > 0
