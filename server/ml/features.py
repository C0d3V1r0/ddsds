# - Извлечение признаков из сырых метрик и логов для ML-моделей
import json


def extract_metrics_features(raw: dict) -> list[float]:
    """- Извлекает числовые признаки из словаря метрик для anomaly detector"""
    cpu = float(raw.get("cpu_total", 0) or 0)
    ram_used = float(raw.get("ram_used", 0) or 0)
    ram_total = float(raw.get("ram_total", 1) or 1)
    ram_percent = (ram_used / ram_total) * 100 if ram_total > 0 else 0
    net_rx = float(raw.get("network_rx", 0) or 0)
    net_tx = float(raw.get("network_tx", 0) or 0)

    load_avg_raw = raw.get("load_avg", "[]")
    if isinstance(load_avg_raw, str):
        try:
            load_avg = json.loads(load_avg_raw)
        except json.JSONDecodeError:
            load_avg = []
    else:
        load_avg = load_avg_raw

    load_1m = float(load_avg[0]) if load_avg else 0

    return [cpu, ram_percent, net_rx, net_tx, load_1m, net_rx + net_tx]


def extract_log_features(line: str) -> str:
    """- Нормализует строку лога для text classifier"""
    return line.strip().lower()
