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