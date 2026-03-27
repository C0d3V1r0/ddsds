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
        event_count=3,
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
    assert anomaly["event_count"] == 3
    assert anomaly["next_run_at"] == 1_700_000_000
