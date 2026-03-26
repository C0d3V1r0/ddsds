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


def get_anomaly_detector() -> AnomalyDetector:
    return _anomaly_detector


def get_classifier() -> AttackClassifier:
    return _attack_classifier


async def init_models(db_path: str) -> None:
    """Инициализация моделей: загружает с диска или обучает с нуля"""
    MODELS_DIR.mkdir(exist_ok=True)

    # Пробуем загрузить anomaly detector с диска
    anomaly_path = MODELS_DIR / "anomaly.joblib"
    if anomaly_path.exists():
        try:
            _anomaly_detector.load(str(anomaly_path))
            _logger.info("Anomaly detector загружен с диска")
        except Exception as exc:
            _logger.warning(f"Ошибка загрузки anomaly detector: {exc}")

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
    cutoff = int(time.time()) - hours * 3600

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM metrics WHERE timestamp > ? ORDER BY timestamp",
            (cutoff,)
        )
        rows = await cursor.fetchall()

    if len(rows) < MIN_TRAINING_SAMPLES:
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
        _logger.warning(f"Poisoned baseline: {event_count} security-событий в окне обучения, пропускаем")
        return False

    data = [extract_metrics_features(dict(row)) for row in rows]
    _anomaly_detector.train(data)

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
