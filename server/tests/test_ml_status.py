# Тесты API-статуса ML-моделей: расширенные причины и служебные поля
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_ml_status_exposes_anomaly_reason_fields(test_app):
    from ml.trainer import _set_anomaly_status

    _set_anomaly_status(
        "insufficient_data",
        "insufficient_data",
        samples_count=12,
        filtered_samples_count=9,
        discarded_samples_count=3,
        event_count=3,
        max_event_count=7,
        maintenance_event_count=2,
        host_profile="web",
        filter_window_seconds=120,
        maintenance_window_seconds=300,
        dataset_quality_score=67,
        dataset_quality_label="medium",
        dataset_noise_label="stressed",
        weighted_event_pressure=5,
        excluded_windows_count=4,
        next_run_at=1_700_000_000,
    )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ml/status")

    assert resp.status_code == 200
    data = resp.json()
    anomaly = data["anomaly_detector"]
    assert anomaly["status"] == "insufficient_data"
    assert anomaly["reason_code"] == "insufficient_data"
    assert anomaly["samples_count"] == 12
    assert anomaly["filtered_samples_count"] == 9
    assert anomaly["discarded_samples_count"] == 3
    assert anomaly["event_count"] == 3
    assert anomaly["max_event_count"] == 7
    assert anomaly["maintenance_event_count"] == 2
    assert anomaly["host_profile"] == "web"
    assert anomaly["filter_window_seconds"] == 120
    assert anomaly["maintenance_window_seconds"] == 300
    assert anomaly["dataset_quality_score"] == 67
    assert anomaly["dataset_quality_label"] == "medium"
    assert anomaly["dataset_noise_label"] == "stressed"
    assert anomaly["weighted_event_pressure"] == 5
    assert anomaly["excluded_windows_count"] == 4
    assert anomaly["next_run_at"] == 1_700_000_000
