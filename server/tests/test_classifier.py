# Тесты классификатора атак на базе TF-IDF + LinearSVC
import os
import pytest
from ml.classifier import AttackClassifier

# Путь к датасету относительно корня сервера
_BASE_CSV = os.path.join(os.path.dirname(__file__), "..", "ml", "datasets", "base_attacks.csv")


@pytest.fixture
def trained_classifier():
    """Возвращает классификатор обученный на базовом датасете"""
    classifier = AttackClassifier()
    classifier.train_from_csv(_BASE_CSV)
    return classifier


def test_classifier_not_ready_before_training():
    """Проверяет что классификатор не готов до обучения"""
    classifier = AttackClassifier()
    assert classifier.is_ready() is False


def test_classifier_predict_before_training():
    """Проверяет безопасный ответ до обучения"""
    classifier = AttackClassifier()
    result = classifier.predict("some text")
    assert result["label"] == "unknown"
    assert result["confidence"] == 0.0


def test_classifier_predicts_ssh(trained_classifier):
    """Проверяет классификацию SSH brute force"""
    result = trained_classifier.predict("Failed password for root from 192.168.1.1 port 22 ssh2")
    assert result["label"] == "ssh_brute_force"


def test_classifier_predicts_sqli(trained_classifier):
    """Проверяет классификацию SQL injection"""
    result = trained_classifier.predict("GET /page?id=1 UNION SELECT password FROM users")
    assert result["label"] == "sqli"


def test_classifier_predicts_xss(trained_classifier):
    """Проверяет классификацию XSS"""
    result = trained_classifier.predict("GET /page?q=<script>alert('xss')</script>")
    assert result["label"] == "xss"


def test_classifier_predicts_path_traversal(trained_classifier):
    """Проверяет классификацию path traversal"""
    result = trained_classifier.predict("GET /page?file=../../../../etc/passwd")
    assert result["label"] == "path_traversal"


def test_classifier_predicts_normal(trained_classifier):
    """Проверяет классификацию нормального трафика"""
    result = trained_classifier.predict("GET /index.html HTTP/1.1 200")
    assert result["label"] == "normal"


def test_classifier_save_load(trained_classifier, tmp_path):
    """Проверяет сохранение и загрузку pipeline с диска"""
    path = str(tmp_path / "classifier.joblib")
    trained_classifier.save(path)

    classifier_loaded = AttackClassifier()
    classifier_loaded.load(path)
    assert classifier_loaded.is_ready() is True

    result = classifier_loaded.predict("Failed password for root from 10.0.0.1")
    assert result["label"] == "ssh_brute_force"
