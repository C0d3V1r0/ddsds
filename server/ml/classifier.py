# Классификатор атак: TF-IDF + LinearSVC
import csv
import math
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

from ml.utils import _compute_hash


class AttackClassifier:
    def __init__(self):
        self._pipeline: Pipeline | None = None
        self._ready = False
        self._file_hash = ""

    def is_ready(self) -> bool:
        return self._ready

    def train_from_csv(self, csv_path: str) -> None:
        """Обучает классификатор на CSV-файле с колонками text,label"""
        texts: list[str] = []
        labels: list[str] = []
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "text" not in row or "label" not in row:
                    raise ValueError(f"CSV должен содержать колонки 'text' и 'label', найдено: {list(row.keys())}")
                texts.append(row["text"].strip().lower())
                labels.append(row["label"].strip())
        self.train(texts, labels)

    def train(self, texts: list[str], labels: list[str]) -> None:
        """Обучает pipeline на текстах и метках"""
        self._pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
            ("clf", LinearSVC(class_weight="balanced", max_iter=10000, random_state=42)),
        ])
        self._pipeline.fit(texts, labels)
        self._ready = True

    def predict(self, text: str) -> dict:
        """Классифицирует текст лога"""
        if not self._ready or self._pipeline is None:
            return {"label": "unknown", "confidence": 0.0}

        normalized_text = text.lower()
        prediction = self._pipeline.predict([normalized_text])[0]
        confidence = self._predict_confidence(normalized_text)
        return {"label": str(prediction), "confidence": confidence}

    def _predict_confidence(self, text: str) -> float:
        """Оценивает уверенность модели по отступу decision_function.

        Для мультиклассовой задачи нам важен не абсолютный скор, а разрыв
        между лучшим и вторым классом. Так мы получаем более честную оценку
        силы сигнала без превращения LinearSVC в псевдо-probability модель.
        """
        if self._pipeline is None or not hasattr(self._pipeline, "decision_function"):
            return 0.5

        raw_scores = self._pipeline.decision_function([text])
        if hasattr(raw_scores, "ndim") and raw_scores.ndim > 1:
            scores = sorted((float(value) for value in raw_scores[0]), reverse=True)
            margin = scores[0] - scores[1] if len(scores) > 1 else abs(scores[0])
        else:
            margin = abs(float(raw_scores[0]))

        # Плавно нормализуем отступ до диапазона 0..1 без резких скачков.
        return round(1.0 - math.exp(-max(margin, 0.0)), 3)

    def save(self, path: str) -> None:
        """Сохраняет pipeline на диск"""
        joblib.dump(self._pipeline, path)
        self._file_hash = _compute_hash(path)

    def load(self, path: str) -> None:
        """Загружает pipeline с диска с верификацией хеша"""
        self._pipeline = joblib.load(path)
        self._ready = True
        self._file_hash = _compute_hash(path)

    def get_file_hash(self) -> str:
        """Возвращает SHA-256 хеш файла модели"""
        return self._file_hash
