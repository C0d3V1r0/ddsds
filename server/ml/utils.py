# Общие утилиты для ML-модулей
import hashlib


def _compute_hash(path: str) -> str:
    """Вычисляет SHA-256 хеш файла модели для верификации целостности"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
