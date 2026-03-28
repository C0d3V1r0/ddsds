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
            "filtered_samples_count": anomaly_status["filtered_samples_count"],
            "discarded_samples_count": anomaly_status["discarded_samples_count"],
            "required_samples": anomaly_status["required_samples"],
            "event_count": anomaly_status["event_count"],
            "max_event_count": anomaly_status["max_event_count"],
            "maintenance_event_count": anomaly_status["maintenance_event_count"],
            "host_profile": anomaly_status["host_profile"],
            "filter_window_seconds": anomaly_status["filter_window_seconds"],
            "maintenance_window_seconds": anomaly_status["maintenance_window_seconds"],
            "dataset_quality_score": anomaly_status["dataset_quality_score"],
            "dataset_quality_label": anomaly_status["dataset_quality_label"],
            "dataset_noise_label": anomaly_status["dataset_noise_label"],
            "weighted_event_pressure": anomaly_status["weighted_event_pressure"],
            "excluded_windows_count": anomaly_status["excluded_windows_count"],
            "updated_at": anomaly_status["updated_at"],
            "next_run_at": anomaly_status["next_run_at"],
        },
        "attack_classifier": {
            "ready": get_classifier().is_ready(),
        },
    }
