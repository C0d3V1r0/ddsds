# - API-эндпоинт для статуса ML-моделей
from fastapi import APIRouter
from ml.trainer import get_anomaly_detector, get_classifier

router = APIRouter(prefix="/api")


@router.get("/ml/status")
async def ml_status():
    """- Возвращает статус ML-моделей"""
    return {
        "anomaly_detector": {
            "ready": get_anomaly_detector().is_ready(),
        },
        "attack_classifier": {
            "ready": get_classifier().is_ready(),
        },
    }
