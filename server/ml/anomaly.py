# - Детектор аномалий на базе Isolation Forest
import hashlib
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest


def _compute_hash(path: str) -> str:
    """- Вычисляет SHA-256 хеш файла модели для верификации целостности"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class AnomalyDetector:
    def __init__(self, contamination: float = 0.05):
        self._model: IsolationForest | None = None
        self._contamination = contamination
        self._ready = False
        self._file_hash = ""

    def is_ready(self) -> bool:
        return self._ready

    def train(self, data: list[list[float]]) -> None:
        """- Обучает модель на нормальных данных метрик"""
        X = np.array(data)
        self._model = IsolationForest(
            contamination=self._contamination,
            random_state=42,
            n_estimators=100,
        )
        self._model.fit(X)
        self._ready = True

    def predict(self, features: list[float]) -> dict:
        """- Возвращает предсказание: является ли набор метрик аномалией"""
        if not self._ready or self._model is None:
            return {"is_anomaly": False, "score": 0.0}

        X = np.array([features])
        score = self._model.decision_function(X)[0]
        prediction = self._model.predict(X)[0]

        return {
            "is_anomaly": bool(prediction == -1),
            "score": float(score),
        }

    def save(self, path: str) -> None:
        """- Сохраняет обученную модель на диск"""
        if self._model is None:
            raise RuntimeError("# - Модель не обучена, сохранение невозможно")
        joblib.dump(self._model, path)
        self._file_hash = _compute_hash(path)

    def load(self, path: str) -> None:
        """- Загружает модель с диска с верификацией хеша"""
        self._model = joblib.load(path)
        self._ready = True
        self._file_hash = _compute_hash(path)

    def get_file_hash(self) -> str:
        """- Возвращает SHA-256 хеш файла модели"""
        return self._file_hash
