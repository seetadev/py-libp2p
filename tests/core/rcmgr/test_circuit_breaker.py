"""
Tests for the rcmgr circuit_breaker module.
"""

from __future__ import annotations

import time

import pytest

from libp2p.rcmgr.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
)


class TestCircuitBreakerState:
    def test_state_values(self) -> None:
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerClosed:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.is_closed() is True
        assert cb.is_open() is False
        assert cb.is_half_open() is False

    def test_call_succeeds(self) -> None:
        cb = CircuitBreaker()
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.failure_count == 0

    def test_passes_args_and_kwargs(self) -> None:
        cb = CircuitBreaker()
        result = cb.call(lambda a, b, c=0: a + b + c, 1, 2, c=3)
        assert result == 6

    def test_unexpected_exception_is_not_counted(self) -> None:
        # Default expected_exception is Exception, so all are counted
        cb = CircuitBreaker(expected_exception=ValueError)
        with pytest.raises(KeyError):
            cb.call(lambda: {}["missing"])
        # KeyError is not the expected type, so failure_count stays at 0
        assert cb.failure_count == 0
        assert cb.is_closed() is True


class TestCircuitBreakerOpens:
    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, timeout=60.0)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert cb.is_open() is True
        with pytest.raises(CircuitBreakerError):
            cb.call(lambda: "should not run")

    def test_open_circuit_does_not_call_function(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, timeout=60.0)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        called = []
        with pytest.raises(CircuitBreakerError):
            cb.call(lambda: called.append(1))
        assert called == []


class TestCircuitBreakerHalfOpen:
    def test_transitions_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert cb.is_open() is True
        time.sleep(0.06)
        # First call after timeout transitions to half-open and runs
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.is_closed() is True  # success closes the circuit
        assert cb.failure_count == 0

    def test_failure_in_half_open_reopens(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        time.sleep(0.06)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("again")))
        assert cb.is_open() is True


class TestCircuitBreakerStats:
    def test_get_stats_includes_state_and_counts(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, timeout=30.0)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        stats = cb.get_stats()
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 1
        assert stats["failure_threshold"] == 5
        assert stats["timeout"] == 30.0
        assert stats["time_since_last_failure"] is not None

    def test_reset_returns_to_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, timeout=60.0)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert cb.is_open() is True
        cb.reset()
        assert cb.is_closed() is True
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
