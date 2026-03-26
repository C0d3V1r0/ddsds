# Тесты детектора аномалий на базе Isolation Forest
import numpy as np
from ml.anomaly import AnomalyDetector


def test_detector_not_ready_before_training():
    """Проверяет что детектор не готов до обучения"""
    detector = AnomalyDetector()
    assert detector.is_ready() is False


def test_detector_predict_before_training():
    """Проверяет безопасный ответ до обучения"""
    detector = AnomalyDetector()
    result = detector.predict([30, 50, 1000, 500, 1.0, 1500])
    assert result["is_anomaly"] is False
    assert result["score"] == 0.0


def test_detector_train_and_predict_normal():
    """Проверяет что нормальные данные не детектируются как аномалии"""
    detector = AnomalyDetector()
    np.random.seed(42)
    normal_data = np.random.normal(
        loc=[30, 50, 1000, 500, 1.0, 1500],
        scale=[5, 10, 200, 100, 0.3, 300],
        size=(500, 6),
    )
    detector.train(normal_data.tolist())
    assert detector.is_ready() is True
    result = detector.predict([30, 50, 1000, 500, 1.0, 1500])
    assert result["is_anomaly"] is False


def test_detector_detects_anomaly():
    """Проверяет что экстремальные значения определяются как аномалия"""
    detector = AnomalyDetector()
    np.random.seed(42)
    normal_data = np.random.normal(
        loc=[30, 50, 1000, 500, 1.0, 1500],
        scale=[5, 10, 200, 100, 0.3, 300],
        size=(500, 6),
    )
    detector.train(normal_data.tolist())
    result = detector.predict([99, 99, 999999, 999999, 50.0, 1999998])
    assert result["is_anomaly"] is True


def test_detector_save_load(tmp_path):
    """Проверяет сохранение и загрузку модели с диска"""
    detector = AnomalyDetector()
    np.random.seed(42)
    data = np.random.normal(
        loc=[30, 50, 1000, 500, 1.0, 1500],
        scale=[5, 10, 200, 100, 0.3, 300],
        size=(200, 6),
    )
    detector.train(data.tolist())
    path = str(tmp_path / "anomaly.joblib")
    detector.save(path)

    detector_loaded = AnomalyDetector()
    detector_loaded.load(path)
    assert detector_loaded.is_ready() is True

    # Проверяем что загруженная модель даёт те же результаты
    result_original = detector.predict([30, 50, 1000, 500, 1.0, 1500])
    result_loaded = detector_loaded.predict([30, 50, 1000, 500, 1.0, 1500])
    assert result_original["is_anomaly"] == result_loaded["is_anomaly"]
