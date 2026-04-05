from collections import deque, defaultdict
from datetime import datetime, timedelta
import numpy as np
from models import MetricIn

# Хранилище: имя метрики -> deque последних значений (по умолчанию 1000)
_raw_metrics = defaultdict(lambda: deque(maxlen=1000))
_aggregates = {}  # имя метрики -> последний агрегат

def add_metric(metric: MetricIn):
    key = metric.name
    _raw_metrics[key].append((metric.timestamp, metric.value, metric.tags))
    # при необходимости можно сразу пересчитать агрегат, но лучше фоном

def get_recent(name: str, seconds: int = 300):
    """Возвращает значения за последние N секунд."""
    cutoff = datetime.now() - timedelta(seconds=seconds)
    result = []
    for ts, val, tags in _raw_metrics.get(name, []):
        if ts > cutoff:
            result.append((ts, val, tags))
    return result

def compute_aggregate(name: str) -> dict:
    values = [v for _, v, _ in _raw_metrics.get(name, [])]
    if not values:
        return None
    arr = np.array(values)
    return {
        "mean": float(np.mean(arr)),
        "max": float(np.max(arr)),
        "min": float(np.min(arr)),
        "sum": float(np.sum(arr)),
        "p95": float(np.percentile(arr, 95)) if len(arr) >= 20 else None,
        "last_update": datetime.now()
    }

def update_all_aggregates():
    for name in list(_raw_metrics.keys()):
        agg = compute_aggregate(name)
        if agg:
            _aggregates[name] = agg

def get_aggregate(name: str):
    return _aggregates.get(name)

def list_metrics():
    return list(_raw_metrics.keys())
