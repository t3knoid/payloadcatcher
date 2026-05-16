from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import Depends

from app.core.config import Settings, get_settings


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int, clock: Callable[[], float] | None = None) -> None:
        self.limit_per_minute = limit_per_minute
        self.clock = clock or monotonic
        self.window_seconds = 60.0
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check_and_consume(self, key: str) -> int | None:
        if self.limit_per_minute <= 0:
            return None

        now = self.clock()
        window_start = now - self.window_seconds

        with self._lock:
            events = self._events[key]
            while events and events[0] <= window_start:
                events.popleft()

            if len(events) >= self.limit_per_minute:
                retry_after = max(1, ceil((events[0] + self.window_seconds) - now))
                return retry_after

            events.append(now)
            return None


@lru_cache
def _get_cached_rate_limiter(limit_per_minute: int) -> InMemoryRateLimiter:
    return InMemoryRateLimiter(limit_per_minute=limit_per_minute)


def get_hook_rate_limiter(settings: Settings = Depends(get_settings)) -> InMemoryRateLimiter:
    return _get_cached_rate_limiter(settings.rate_limit_per_minute)