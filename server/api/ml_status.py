# API-эндпоинт для статуса ML-моделей
from fastapi import APIRouter
from ml.trainer import get_anomaly_detector, get_anomaly_status, get_classifier

router = APIRouter(prefix="/api")


@router.get("/ml/status")
async def ml_status():
    """Возвращает статус ML-моделей."""
    anomaly_status = get_anomaly_status()
    return {
        "anomaly_detector": {
            "ready": get_anomaly_detector().is_ready(),
            "status": anomaly_status["status"],
            "reason_code": anomaly_status["reason_code"],
            "samples_count": anomaly_status["samples_count"],
            "required_samples": anomaly_status["required_samples"],
            "event_count": anomaly_status["event_count"],
            "max_event_count": anomaly_status["max_event_count"],
            "updated_at": anomaly_status["updated_at"],
            "next_run_at": anomaly_status["next_run_at"],
        },
        "attack_classifier": {
            "ready": get_classifier().is_ready(),
        },
    }
