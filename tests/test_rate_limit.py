from concurrent.futures import ThreadPoolExecutor

from app.infrastructure.rate_limit import InMemoryRateLimiter


def test_rate_limiter_evicts_stale_keys_during_cleanup() -> None:
    current_time = {"value": 0.0}
    limiter = InMemoryRateLimiter(1, clock=lambda: current_time["value"])

    assert limiter.check_and_consume("203.0.113.10") is None
    assert "203.0.113.10" in limiter._events

    current_time["value"] = 61.0

    assert limiter.check_and_consume("198.51.100.8") is None
    assert "203.0.113.10" not in limiter._events
    assert "198.51.100.8" in limiter._events


def test_rate_limiter_allows_only_limit_under_concurrency() -> None:
    limiter = InMemoryRateLimiter(3)

    def consume(_: int) -> int | None:
        return limiter.check_and_consume("203.0.113.10")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(consume, range(8)))

    assert sum(result is None for result in results) == 3
    assert sum(result is not None for result in results) == 5