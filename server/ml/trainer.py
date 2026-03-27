# Оркестратор обучения ML-моделей: загрузка, обучение, версионирование
import logging
import time
from pathlib import Path

import aiosqlite

from ml.anomaly import AnomalyDetector
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
    "required_samples": MIN_TRAINING_SAMPLES,
    "event_count": 0,
    "max_event_count": MAX_EVENTS_CLEAN_BASELINE,
    "updated_at": 0,
    "next_run_at": None,
}


def _set_anomaly_status(
    status: str,
    reason_code: str,
    *,
    samples_count: int = 0,
    event_count: int = 0,
    next_run_at: int | None = None,
) -> None:
    global _anomaly_status
    _anomaly_status = {
        "status": status,
        "reason_code": reason_code,
        "samples_count": samples_count,
        "required_samples": MIN_TRAINING_SAMPLES,
        "event_count": event_count,
        "max_event_count": MAX_EVENTS_CLEAN_BASELINE,
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


async def train_anomaly_from_db(db_path: str, hours: int = 24) -> bool:
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

    if len(rows) < MIN_TRAINING_SAMPLES:
        _set_anomaly_status(
            "insufficient_data",
            "insufficient_data",
            samples_count=len(rows),
        )
        _logger.info(f"Недостаточно метрик для обучения: {len(rows)} (нужно минимум {MIN_TRAINING_SAMPLES})")
        return False

    # Проверка на poisoned baseline: если много security-событий, отложить обучение
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM security_events WHERE timestamp > ?",
            (cutoff,)
        )
        row = await cursor.fetchone()
        event_count = row[0] if row else 0

    if event_count > MAX_EVENTS_CLEAN_BASELINE:
        _set_anomaly_status(
            "postponed",
            "poisoned_baseline",
            samples_count=len(rows),
            event_count=event_count,
        )
        _logger.warning(f"Poisoned baseline: {event_count} security-событий в окне обучения, пропускаем")
        return False

    data = [extract_metrics_features(dict(row)) for row in rows]
    _anomaly_detector.train(data)
    _set_anomaly_status(
        "running",
        "ready",
        samples_count=len(rows),
        event_count=event_count,
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
        len(rows), 0.0, str(anomaly_path), _anomaly_detector.get_file_hash()
    )
    _logger.info(f"Anomaly detector обучен на {len(rows)} записях метрик")
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
