# Nullius v2 — Phase 4: ML Module

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ML-powered anomaly detection (Isolation Forest) and attack classification (TF-IDF + LinearSVC) to the FastAPI backend.

**Architecture:** ML module runs inside FastAPI process. Anomaly detector trains on first 24h of metrics, then scores in real-time. Attack classifier ships with a pre-trained base model, fine-tunes on local logs. Models stored as .joblib files, versioned in SQLite.

**Tech Stack:** scikit-learn, joblib, numpy, pandas

**Spec:** `docs/superpowers/specs/2026-03-25-nullius-v2-design.md`
**Depends on:** Phase 1 (Backend must be complete)

---

## File Structure

```
server/ml/
├── __init__.py
├── anomaly.py              # Isolation Forest: train, predict, retrain
├── classifier.py           # TF-IDF + LinearSVC: train, predict
├── trainer.py              # Training orchestrator: schedule, versioning
├── features.py             # Feature extraction from raw metrics/logs
├── datasets/
│   └── base_attacks.csv    # Pre-built attack dataset (ships with product)
└── models/                 # Saved .joblib files (gitignored)
```

---

### Task 1: Feature Extraction

**Files:**
- Create: `server/ml/__init__.py`
- Create: `server/ml/features.py`
- Create: `server/tests/test_features.py`

- [ ] **Step 1: Write failing test**

```python
# server/tests/test_features.py
import pytest
from ml.features import extract_metrics_features, extract_log_features

def test_extract_metrics_features():
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
    assert features[0] == 45.0  # cpu
    assert features[1] == pytest.approx(50.0)  # ram percent

def test_extract_log_features():
    line = "Failed password for root from 10.0.0.1 port 22 ssh2"
    text = extract_log_features(line)
    assert isinstance(text, str)
    assert len(text) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_features.py -v`

- [ ] **Step 3: Implement features.py**

```python
# server/ml/__init__.py
```

```python
# server/ml/features.py
import json

def extract_metrics_features(raw: dict) -> list[float]:
    cpu = float(raw.get("cpu_total", 0) or 0)
    ram_used = float(raw.get("ram_used", 0) or 0)
    ram_total = float(raw.get("ram_total", 1) or 1)
    ram_percent = (ram_used / ram_total) * 100 if ram_total > 0 else 0
    net_rx = float(raw.get("network_rx", 0) or 0)
    net_tx = float(raw.get("network_tx", 0) or 0)
    load_avg_raw = raw.get("load_avg", "[]")
    if isinstance(load_avg_raw, str):
        load_avg = json.loads(load_avg_raw)
    else:
        load_avg = load_avg_raw
    load_1m = float(load_avg[0]) if load_avg else 0
    return [cpu, ram_percent, net_rx, net_tx, load_1m, net_rx + net_tx]

def extract_log_features(line: str) -> str:
    return line.strip().lower()
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 2: Anomaly Detector (Isolation Forest)

**Files:**
- Create: `server/ml/anomaly.py`
- Create: `server/tests/test_anomaly.py`

- [ ] **Step 1: Write failing test**

```python
# server/tests/test_anomaly.py
import pytest
import numpy as np
from ml.anomaly import AnomalyDetector

def test_detector_not_ready_before_training():
    d = AnomalyDetector()
    assert d.is_ready() is False

def test_detector_train_and_predict_normal():
    d = AnomalyDetector()
    # Generate normal data
    np.random.seed(42)
    normal_data = np.random.normal(loc=[30, 50, 1000, 500, 1.0, 1500], scale=[5, 10, 200, 100, 0.3, 300], size=(500, 6))
    d.train(normal_data.tolist())
    assert d.is_ready() is True
    # Normal sample should not be anomaly
    result = d.predict([30, 50, 1000, 500, 1.0, 1500])
    assert result["is_anomaly"] is False

def test_detector_detects_anomaly():
    d = AnomalyDetector()
    np.random.seed(42)
    normal_data = np.random.normal(loc=[30, 50, 1000, 500, 1.0, 1500], scale=[5, 10, 200, 100, 0.3, 300], size=(500, 6))
    d.train(normal_data.tolist())
    # Extreme outlier
    result = d.predict([99, 99, 999999, 999999, 50.0, 1999998])
    assert result["is_anomaly"] is True

def test_detector_save_load(tmp_path):
    d = AnomalyDetector()
    np.random.seed(42)
    data = np.random.normal(loc=[30, 50, 1000, 500, 1.0, 1500], scale=[5, 10, 200, 100, 0.3, 300], size=(200, 6))
    d.train(data.tolist())
    path = str(tmp_path / "anomaly.joblib")
    d.save(path)
    d2 = AnomalyDetector()
    d2.load(path)
    assert d2.is_ready() is True
```

- [ ] **Step 2: Implement anomaly.py**

```python
# server/ml/anomaly.py
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

class AnomalyDetector:
    def __init__(self, contamination: float = 0.05):
        self._model: IsolationForest | None = None
        self._contamination = contamination
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def train(self, data: list[list[float]]) -> None:
        X = np.array(data)
        self._model = IsolationForest(
            contamination=self._contamination,
            random_state=42,
            n_estimators=100,
        )
        self._model.fit(X)
        self._ready = True

    def predict(self, features: list[float]) -> dict:
        if not self._ready or self._model is None:
            return {"is_anomaly": False, "score": 0.0}
        X = np.array([features])
        score = self._model.decision_function(X)[0]
        prediction = self._model.predict(X)[0]
        return {
            "is_anomaly": prediction == -1,
            "score": float(score),
        }

    def save(self, path: str) -> None:
        joblib.dump(self._model, path)

    def load(self, path: str) -> None:
        self._model = joblib.load(path)
        self._ready = True
```

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

---

### Task 3: Attack Classifier (TF-IDF + LinearSVC)

**Files:**
- Create: `server/ml/classifier.py`
- Create: `server/tests/test_classifier.py`
- Create: `server/ml/datasets/base_attacks.csv`

- [ ] **Step 1: Create base dataset**

```csv
text,label
Failed password for root from 10.0.0.1 port 22 ssh2,ssh_brute_force
Failed password for admin from 10.0.0.2 port 22 ssh2,ssh_brute_force
Invalid user test from 10.0.0.3 port 22,ssh_brute_force
GET /page?id=1 OR 1=1-- HTTP/1.1,sqli
GET /search?q=UNION SELECT * FROM users,sqli
POST /login username=admin' OR '1'='1,sqli
GET /page?q=<script>alert(1)</script>,xss
GET /search?q=<img onerror=alert(1)>,xss
GET /../../etc/passwd HTTP/1.1,path_traversal
GET /..%2f..%2fetc%2fpasswd,path_traversal
GET / HTTP/1.1 200,normal
POST /api/login HTTP/1.1 200,normal
GET /static/style.css HTTP/1.1 200,normal
```

- [ ] **Step 2: Write failing test**

```python
# server/tests/test_classifier.py
import pytest
from ml.classifier import AttackClassifier

@pytest.fixture
def trained_classifier():
    c = AttackClassifier()
    c.train_from_csv("ml/datasets/base_attacks.csv")
    return c

def test_classifier_not_ready_before_training():
    c = AttackClassifier()
    assert c.is_ready() is False

def test_classifier_predicts_ssh(trained_classifier):
    result = trained_classifier.predict("Failed password for root from 192.168.1.1 port 22 ssh2")
    assert result["label"] == "ssh_brute_force"

def test_classifier_predicts_sqli(trained_classifier):
    result = trained_classifier.predict("GET /page?id=1 UNION SELECT password FROM users")
    assert result["label"] == "sqli"

def test_classifier_predicts_normal(trained_classifier):
    result = trained_classifier.predict("GET /index.html HTTP/1.1 200")
    assert result["label"] == "normal"

def test_classifier_save_load(trained_classifier, tmp_path):
    path = str(tmp_path / "classifier.joblib")
    trained_classifier.save(path)
    c2 = AttackClassifier()
    c2.load(path)
    assert c2.is_ready() is True
    result = c2.predict("Failed password for root from 10.0.0.1")
    assert result["label"] == "ssh_brute_force"
```

- [ ] **Step 3: Implement classifier.py**

```python
# server/ml/classifier.py
import csv
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

class AttackClassifier:
    def __init__(self):
        self._pipeline: Pipeline | None = None
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def train_from_csv(self, csv_path: str) -> None:
        texts, labels = [], []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.append(row["text"].strip().lower())
                labels.append(row["label"].strip())
        self.train(texts, labels)

    def train(self, texts: list[str], labels: list[str]) -> None:
        self._pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
            ("clf", LinearSVC(class_weight="balanced", max_iter=10000, random_state=42)),
        ])
        self._pipeline.fit(texts, labels)
        self._ready = True

    def predict(self, text: str) -> dict:
        if not self._ready or self._pipeline is None:
            return {"label": "unknown", "confidence": 0.0}
        prediction = self._pipeline.predict([text.lower()])[0]
        return {"label": prediction}

    def save(self, path: str) -> None:
        joblib.dump(self._pipeline, path)

    def load(self, path: str) -> None:
        self._pipeline = joblib.load(path)
        self._ready = True
```

- [ ] **Step 4: Run tests, verify pass**
- [ ] **Step 5: Commit**

---

### Task 4: Training Orchestrator

**Files:**
- Create: `server/ml/trainer.py`
- Create: `server/tests/test_trainer.py`

- [ ] **Step 1: Write test for trainer**

Tests: `init_models` loads or trains models, `retrain_anomaly` updates model and bumps version in DB, poisoned baseline detection resets training.

- [ ] **Step 2: Implement trainer.py**

Orchestrator that:
- On startup: loads existing models from disk, or trains from scratch
- Anomaly: collects 24h of metrics from DB, trains, saves, records in `ml_models` table
- Classifier: loads base model, optionally fine-tunes on local labeled data
- Retrain: scheduled every 7 days for anomaly, triggered manually for classifier
- Poisoned baseline: if `security_events` count > 10 during training window, discard and restart

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

---

### Task 5: Wire ML into Event Pipeline

**Files:**
- Modify: `server/ws/agent.py`
- Modify: `server/main.py`
- Modify: `server/api/health.py`
- Create: `server/api/ml_status.py`

- [ ] **Step 1: Add ML scoring to metrics handler**

In `_handle_metrics()`, after writing to DB, score with anomaly detector. If anomaly detected, create security event.

- [ ] **Step 2: Add ML classification to log handler**

In `_handle_log()`, after rule-based detection, also run classifier as second opinion. If classifier detects attack but rules didn't, create event with severity low + tag "ml_detection".

- [ ] **Step 3: Add /api/ml/status endpoint**

Returns: model names, versions, trained_at, is_ready, training progress.

- [ ] **Step 4: Update health endpoint**

Add ML status to health response.

- [ ] **Step 5: Wire training schedule into main.py lifespan**

Background task: check if anomaly model needs training (24h baseline) or retraining (7-day cycle).

- [ ] **Step 6: Run all tests**
- [ ] **Step 7: Commit**

---

### Task 6: Expand Base Dataset

- [ ] **Step 1: Add more training examples to base_attacks.csv**

Expand to ~200+ examples per class using:
- SSH: variations of `Failed password`, `Invalid user`, `Connection closed by authenticating user`
- SQLi: OWASP patterns, blind SQLi, time-based, error-based
- XSS: reflected, stored, DOM-based patterns
- Path traversal: Windows and Unix variants, URL-encoded
- Port scan: Nmap output patterns, SYN flood indicators
- Normal: typical nginx access log lines, auth success

- [ ] **Step 2: Retrain and verify accuracy**

```python
from sklearn.model_selection import cross_val_score
scores = cross_val_score(pipeline, texts, labels, cv=5)
print(f"Accuracy: {scores.mean():.2f} (+/- {scores.std():.2f})")
```

Target: >85% cross-validation accuracy.

- [ ] **Step 3: Commit**
