from __future__ import annotations

from collections import Counter
from functools import lru_cache
from threading import Lock


class InMemoryMetrics:
    def __init__(self) -> None:
        self._counters: Counter[str] = Counter()
        self._lock = Lock()

    def increment(self, metric_name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[metric_name] += value

    def get(self, metric_name: str) -> int:
        with self._lock:
            return self._counters[metric_name]


@lru_cache
def get_metrics() -> InMemoryMetrics:
    return InMemoryMetrics()