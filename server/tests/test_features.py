# Тесты извлечения признаков из метрик и логов
import pytest
from ml.features import extract_metrics_features, extract_log_features


def test_extract_metrics_features_basic():
    """Проверяет корректность извлечения признаков из стандартных метрик"""
    raw = {
        "cpu_total": 45.0,
        "ram_used": 4096,
        "ram_total": 8192,
        "network_rx": 50000,
        "network_tx": 30000,
        "load_avg": "[1.2, 0.8, 0.5]",
    }
    features = extract_metrics_features(raw)
    assert len(features) == 6
    assert features[0] == 45.0
    assert features[1] == pytest.approx(50.0)
    assert features[2] == 50000.0
    assert features[3] == 30000.0
    assert features[4] == pytest.approx(1.2)
    assert features[5] == pytest.approx(80000.0)


def test_extract_metrics_features_missing_fields():
    """Проверяет обработку пустого словаря метрик"""
    features = extract_metrics_features({})
    assert len(features) == 6
    assert features[0] == 0.0
    assert features[1] == 0.0


def test_extract_metrics_features_list_load_avg():
    """Проверяет обработку load_avg как списка вместо строки"""
    raw = {
        "cpu_total": 10.0,
        "ram_used": 1024,
        "ram_total": 4096,
        "network_rx": 100,
        "network_tx": 200,
        "load_avg": [2.5, 1.0, 0.5],
    }
    features = extract_metrics_features(raw)
    assert features[4] == pytest.approx(2.5)


def test_extract_log_features():
    """Проверяет нормализацию строки лога"""
    line = "  Failed Password for Root from 10.0.0.1 port 22 ssh2  "
    text = extract_log_features(line)
    assert isinstance(text, str)
    assert text == "failed password for root from 10.0.0.1 port 22 ssh2"


def test_extract_log_features_empty():
    """Проверяет обработку пустой строки"""
    assert extract_log_features("") == ""
    assert extract_log_features("   ") == ""
