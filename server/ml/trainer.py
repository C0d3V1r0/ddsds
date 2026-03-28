# Оркестратор обучения ML-моделей: загрузка, обучение, версионирование
import logging
import time
from pathlib import Path

import aiosqlite

from ml.anomaly import AnomalyDetector
from ml.baseline import build_baseline_dataset
from ml.classifier import AttackClassifier
from ml.features import extract_metrics_features

_logger = logging.getLogger("nullius.ml.trainer")

_anomaly_detector = AnomalyDetector()
_attack_classifier = AttackClassifier()

MODELS_DIR = Path(__file__).parent / "models"
DATASETS_DIR = Path(__file__).parent / "datasets"

# Минимум метрик для обучения anomaly detector
MIN_TRAINING_SAMPLES = 100
# Максимум security-событий в окне обучения (защита от poisoned baseline)
MAX_EVENTS_CLEAN_BASELINE = 10

_anomaly_status: dict[str, object] = {
    "status": "pending",
    "reason_code": "waiting_for_first_run",
    "samples_count": 0,
    "filtered_samples_count": 0,
    "discarded_samples_count": 0,
    "required_samples": MIN_TRAINING_SAMPLES,
    "event_count": 0,
    "max_event_count": MAX_EVENTS_CLEAN_BASELINE,
    "maintenance_event_count": 0,
    "host_profile": "generic",
    "filter_window_seconds": 0,
    "maintenance_window_seconds": 0,
    "dataset_quality_score": 0,
    "dataset_quality_label": "low",
    "dataset_noise_label": "clean",
    "weighted_event_pressure": 0,
    "excluded_windows_count": 0,
    "updated_at": 0,
    "next_run_at": None,
}


def _set_anomaly_status(
    status: str,
    reason_code: str,
    *,
    samples_count: int = 0,
    filtered_samples_count: int = 0,
    discarded_samples_count: int = 0,
    required_samples: int = MIN_TRAINING_SAMPLES,
    event_count: int = 0,
    max_event_count: int = MAX_EVENTS_CLEAN_BASELINE,
    maintenance_event_count: int = 0,
    host_profile: str = "generic",
    filter_window_seconds: int = 0,
    maintenance_window_seconds: int = 0,
    dataset_quality_score: int = 0,
    dataset_quality_label: str = "low",
    dataset_noise_label: str = "clean",
    weighted_event_pressure: int = 0,
    excluded_windows_count: int = 0,
    next_run_at: int | None = None,
) -> None:
    global _anomaly_status
    _anomaly_status = {
        "status": status,
        "reason_code": reason_code,
        "samples_count": samples_count,
        "filtered_samples_count": filtered_samples_count,
        "discarded_samples_count": discarded_samples_count,
        "required_samples": required_samples,
        "event_count": event_count,
        "max_event_count": max_event_count,
        "maintenance_event_count": maintenance_event_count,
        "host_profile": host_profile,
        "filter_window_seconds": filter_window_seconds,
        "maintenance_window_seconds": maintenance_window_seconds,
        "dataset_quality_score": dataset_quality_score,
        "dataset_quality_label": dataset_quality_label,
        "dataset_noise_label": dataset_noise_label,
        "weighted_event_pressure": weighted_event_pressure,
        "excluded_windows_count": excluded_windows_count,
        "updated_at": int(time.time()),
        "next_run_at": next_run_at,
    }


def get_anomaly_detector() -> AnomalyDetector:
    return _anomaly_detector


def get_classifier() -> AttackClassifier:
    return _attack_classifier


def get_anomaly_status() -> dict[str, object]:
    return dict(_anomaly_status)


async def init_models(db_path: str) -> None:
    """Инициализация моделей: загружает с диска или обучает с нуля"""
    MODELS_DIR.mkdir(exist_ok=True)

    # Пробуем загрузить anomaly detector с диска
    anomaly_path = MODELS_DIR / "anomaly.joblib"
    if anomaly_path.exists():
        try:
            _anomaly_detector.load(str(anomaly_path))
            _set_anomaly_status("running", "ready")
            _logger.info("Anomaly detector загружен с диска")
        except Exception as exc:
            _set_anomaly_status("failed", "model_load_failed")
            _logger.warning(f"Ошибка загрузки anomaly detector: {exc}")
    else:
        _set_anomaly_status("pending", "waiting_for_first_run")

    # Пробуем загрузить classifier с диска, или обучаем на базовом датасете
    classifier_path = MODELS_DIR / "classifier.joblib"
    if classifier_path.exists():
        try:
            _attack_classifier.load(str(classifier_path))
            _logger.info("Attack classifier загружен с диска")
        except Exception as exc:
            _logger.warning(f"Ошибка загрузки classifier: {exc}")

    if not _attack_classifier.is_ready():
        base_csv = DATASETS_DIR / "base_attacks.csv"
        if base_csv.exists():
            _attack_classifier.train_from_csv(str(base_csv))
            _attack_classifier.save(str(classifier_path))
            await _record_model_version(
                db_path, "attack_classifier", 1, 0, 0.0,
                str(classifier_path), _attack_classifier.get_file_hash()
            )
            _logger.info("Attack classifier обучен на базовом датасете")


def _build_filter_windows(base_buffer_seconds: int) -> tuple[int, ...]:
    """Строит каскад фильтров от строгого к мягкому вокруг security events."""
    windows = {
        max(30, int(base_buffer_seconds)),
        max(30, int(base_buffer_seconds * 0.6)),
        max(30, int(base_buffer_seconds * 0.4)),
        max(30, int(base_buffer_seconds * 0.2)),
    }
    return tuple(sorted(windows, reverse=True))


async def train_anomaly_from_db(
    db_path: str,
    *,
    hours: int = 24,
    min_samples: int = MIN_TRAINING_SAMPLES,
    max_clean_events: int = MAX_EVENTS_CLEAN_BASELINE,
    base_buffer_seconds: int = 300,
    host_profile: str = "generic",
    maintenance_window_seconds: int = 900,
    maintenance_commands: tuple[str, ...] = ("restart_service", "kill_process", "force_kill_process"),
) -> bool:
    """Обучает anomaly detector на метриках из БД за последние N часов"""
    _set_anomaly_status("training", "training_in_progress")
    cutoff = int(time.time()) - hours * 3600

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM metrics WHERE timestamp > ? ORDER BY timestamp",
            (cutoff,)
        )
        rows = await cursor.fetchall()

    if len(rows) < min_samples:
        _set_anomaly_status(
            "insufficient_data",
            "insufficient_data",
            samples_count=len(rows),
            required_samples=min_samples,
            max_event_count=max_clean_events,
            host_profile=host_profile,
            maintenance_window_seconds=maintenance_window_seconds,
        )
        _logger.info(f"Недостаточно метрик для обучения: {len(rows)} (нужно минимум {min_samples})")
        return False

    # Сначала считаем security events в окне, а потом пробуем вырезать загрязнённые интервалы.
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT timestamp, type, severity, action_taken FROM security_events WHERE timestamp > ? ORDER BY timestamp ASC",
            (cutoff,)
        )
        event_rows = await cursor.fetchall()
        maintenance_rows = []
        if maintenance_commands:
            placeholders = ",".join("?" for _ in maintenance_commands)
            maintenance_cursor = await conn.execute(
                f"SELECT timestamp FROM agent_commands WHERE timestamp > ? AND command IN ({placeholders}) ORDER BY timestamp ASC",
                (cutoff, *maintenance_commands),
            )
            maintenance_rows = await maintenance_cursor.fetchall()

    maintenance_timestamps = [int(row[0]) for row in maintenance_rows]
    dataset = build_baseline_dataset(
        rows,
        event_rows,
        maintenance_timestamps=maintenance_timestamps,
        min_samples=min_samples,
        max_clean_events=max_clean_events,
        filter_windows=_build_filter_windows(base_buffer_seconds),
        host_profile=host_profile,
        maintenance_window_seconds=maintenance_window_seconds,
    )

    if dataset["reason_code"] == "poisoned_baseline":
        _set_anomaly_status(
            "postponed",
            "poisoned_baseline",
            samples_count=dataset["total_samples"],
            filtered_samples_count=dataset["clean_samples"],
            discarded_samples_count=dataset["discarded_samples"],
            required_samples=dataset["required_samples"],
            event_count=dataset["event_count"],
            max_event_count=dataset["max_clean_events"],
            maintenance_event_count=dataset["maintenance_event_count"],
            host_profile=dataset["host_profile"],
            filter_window_seconds=dataset["filter_window_seconds"],
            maintenance_window_seconds=dataset["maintenance_window_seconds"],
            dataset_quality_score=dataset["quality_score"],
            dataset_quality_label=dataset["quality_label"],
            dataset_noise_label=dataset["noise_label"],
            weighted_event_pressure=dataset["weighted_event_pressure"],
            excluded_windows_count=dataset["excluded_windows_count"],
        )
        _logger.warning(
            "Poisoned baseline: %s security-событий в окне обучения, даже после очистки clean dataset не сформирован",
            dataset["event_count"],
        )
        return False

    if dataset["reason_code"] == "ready_filtered_baseline":
        _logger.info(
            "Baseline очищен: использовано %s из %s метрик, отброшено %s, буфер %ss, quality=%s/%s",
            dataset["clean_samples"],
            dataset["total_samples"],
            dataset["discarded_samples"],
            dataset["filter_window_seconds"],
            dataset["maintenance_event_count"],
            dataset["quality_score"],
            dataset["quality_label"],
        )

    training_rows = dataset["rows"]
    if len(training_rows) < min_samples:
        _set_anomaly_status(
            "insufficient_data",
            str(dataset["reason_code"]),
            samples_count=dataset["total_samples"],
            filtered_samples_count=dataset["clean_samples"],
            discarded_samples_count=dataset["discarded_samples"],
            required_samples=dataset["required_samples"],
            event_count=dataset["event_count"],
            max_event_count=dataset["max_clean_events"],
            maintenance_event_count=dataset["maintenance_event_count"],
            host_profile=dataset["host_profile"],
            filter_window_seconds=dataset["filter_window_seconds"],
            maintenance_window_seconds=dataset["maintenance_window_seconds"],
            dataset_quality_score=dataset["quality_score"],
            dataset_quality_label=dataset["quality_label"],
            dataset_noise_label=dataset["noise_label"],
            weighted_event_pressure=dataset["weighted_event_pressure"],
            excluded_windows_count=dataset["excluded_windows_count"],
        )
        _logger.info(
            "Недостаточно чистых метрик после подготовки baseline: %s из %s, quality=%s/%s",
            len(training_rows),
            min_samples,
            dataset["quality_score"],
            dataset["quality_label"],
        )
        return False

    data = [extract_metrics_features(dict(row)) for row in training_rows]
    _anomaly_detector.train(data)
    _set_anomaly_status(
        "running",
        str(dataset["reason_code"]),
        samples_count=dataset["total_samples"],
        filtered_samples_count=dataset["clean_samples"],
        discarded_samples_count=dataset["discarded_samples"],
        required_samples=dataset["required_samples"],
        event_count=dataset["event_count"],
        max_event_count=dataset["max_clean_events"],
        maintenance_event_count=dataset["maintenance_event_count"],
        host_profile=dataset["host_profile"],
        filter_window_seconds=dataset["filter_window_seconds"],
        maintenance_window_seconds=dataset["maintenance_window_seconds"],
        dataset_quality_score=dataset["quality_score"],
        dataset_quality_label=dataset["quality_label"],
        dataset_noise_label=dataset["noise_label"],
        weighted_event_pressure=dataset["weighted_event_pressure"],
        excluded_windows_count=dataset["excluded_windows_count"],
    )

    anomaly_path = MODELS_DIR / "anomaly.joblib"
    _anomaly_detector.save(str(anomaly_path))

    # Записываем версию модели в БД
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM ml_models WHERE name = 'anomaly_detector'"
        )
        version_row = await cursor.fetchone()
        current_version = version_row[0] if version_row else 0

    await _record_model_version(
        db_path, "anomaly_detector", current_version + 1,
        len(training_rows), 0.0, str(anomaly_path), _anomaly_detector.get_file_hash()
    )
    _logger.info(
        "Anomaly detector обучен на %s clean samples из %s (quality=%s/%s)",
        len(training_rows),
        dataset["total_samples"],
        dataset["quality_score"],
        dataset["quality_label"],
    )
    return True


async def _record_model_version(
    db_path: str, name: str, version: int,
    samples: int, accuracy: float, file_path: str,
    file_hash: str = ""
) -> None:
    """Записывает информацию о версии модели в БД"""
    async with aiosqlite.connect(db_path) as conn:
        # Деактивируем предыдущие версии
        await conn.execute("UPDATE ml_models SET active = 0 WHERE name = ?", (name,))
        await conn.execute(
            "INSERT INTO ml_models (name, version, trained_at, samples_count, accuracy, file_path, file_hash, active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (name, version, int(time.time()), samples, accuracy, file_path, file_hash)
        )
        await conn.commit()
