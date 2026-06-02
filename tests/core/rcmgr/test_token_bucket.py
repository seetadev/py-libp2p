"""
Tests for the rcmgr token_bucket module.
"""

from __future__ import annotations

import time

import pytest

from libp2p.rcmgr.token_bucket import (
    TokenBucket,
    TokenBucketConfig,
    create_burst_token_bucket,
    create_strict_token_bucket,
    create_token_bucket,
)


class TestTokenBucketConfig:
    def test_valid_config(self) -> None:
        cfg = TokenBucketConfig(refill_rate=1.0, capacity=10.0)
        assert cfg.refill_rate == 1.0
        assert cfg.capacity == 10.0
        assert cfg.initial_tokens == 0.0

    def _base(self, **overrides: object) -> TokenBucketConfig:
        cfg: dict[str, object] = {
            "refill_rate": 1.0,
            "capacity": 10.0,
            "initial_tokens": 0.0,
            "burst_multiplier": 1.0,
            "time_window_seconds": 1.0,
            "min_interval_seconds": 0.001,
            "max_history_size": 1000,
        }
        cfg.update(overrides)
        return TokenBucketConfig(**cfg)  # type: ignore[arg-type]

    def test_valid_config(self) -> None:
        cfg = self._base()
        assert cfg.refill_rate == 1.0
        assert cfg.capacity == 10.0
        assert cfg.initial_tokens == 0.0

    @pytest.mark.parametrize(
        "overrides",
        [
            {"refill_rate": 0},
            {"refill_rate": -1},
            {"capacity": 0},
            {"capacity": -1},
            {"initial_tokens": -1},
            {"initial_tokens": 100},
            {"burst_multiplier": 0.5},
            {"time_window_seconds": 0},
            {"min_interval_seconds": 0},
            {"max_history_size": 0},
        ],
    )
    def test_invalid_config_raises(self, overrides: dict) -> None:
        with pytest.raises(ValueError):
            self._base(**overrides)


class TestTokenBucket:
    def test_initial_state(self) -> None:
        cfg = TokenBucketConfig(refill_rate=1.0, capacity=10.0)
        b = TokenBucket(cfg)
        assert b._tokens == 0.0
        stats = b.get_stats()
        assert stats.current_tokens == 0.0
        assert stats.total_requests == 0
        assert stats.allowed_requests == 0
        assert stats.denied_requests == 0

    def test_consume_with_initial_tokens(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=1.0, capacity=10.0, initial_tokens=5.0
        )
        b = TokenBucket(cfg)
        # 5 initial tokens, capacity 10
        for _ in range(5):
            assert b.try_consume() is True
        assert b.try_consume() is False  # 6th must fail

    def test_consume_respects_capacity(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=1.0, capacity=3.0, initial_tokens=3.0
        )
        b = TokenBucket(cfg)
        for _ in range(3):
            assert b.try_consume() is True
        assert b.try_consume() is False

    def test_refill_advances_tokens(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=10.0,
            capacity=10.0,
            initial_tokens=0.0,
            min_interval_seconds=0.001,
        )
        b = TokenBucket(cfg)
        # Move time forward 0.5s, so 5 tokens should be available
        current = b._last_refill_time
        assert b.try_consume(1.0, current_time=current + 0.5) is True
        assert b._tokens == pytest.approx(4.0, abs=1e-6)

    def test_min_interval_suppresses_small_refills(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=10.0,
            capacity=10.0,
            min_interval_seconds=1.0,
        )
        b = TokenBucket(cfg)
        # Wait less than min_interval -> no refill
        assert b.try_consume(1.0, current_time=b._last_refill_time + 0.5) is False

    def test_consume_method_raises_on_insufficient(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=1.0, capacity=1.0, initial_tokens=1.0
        )
        b = TokenBucket(cfg)
        b.consume(1.0)
        with pytest.raises(ValueError):
            b.consume(1.0)

    def test_stats_to_dict(self) -> None:
        cfg = TokenBucketConfig(refill_rate=2.0, capacity=4.0, initial_tokens=2.0)
        b = TokenBucket(cfg)
        b.try_consume()
        d = b.get_stats().to_dict()
        assert d["refill_rate"] == 2.0
        assert d["capacity"] == 4.0
        assert d["allowed_requests"] == 1
        assert d["denied_requests"] == 0
        assert d["total_requests"] == 1

    def test_get_history_without_monitoring(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=1.0, capacity=5.0, enable_monitoring=False
        )
        b = TokenBucket(cfg)
        b.try_consume()
        history = b.get_history()
        assert history == {"enabled": False}

    def test_get_history_with_monitoring(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=1.0, capacity=5.0, initial_tokens=5.0
        )
        b = TokenBucket(cfg)
        now = time.time()
        b.try_consume(current_time=now)
        b.try_consume(current_time=now)
        history = b.get_history(time_window=10.0)
        assert history["enabled"] is True
        assert history["total_requests"] == 2
        assert history["allowed_requests"] == 2
        assert history["denied_requests"] == 0
        assert history["allow_rate"] == 1.0

    def test_reset(self) -> None:
        cfg = TokenBucketConfig(
            refill_rate=1.0, capacity=5.0, initial_tokens=3.0
        )
        b = TokenBucket(cfg)
        b.try_consume()
        b.try_consume()
        assert b.get_stats().total_requests == 2
        b.reset()
        assert b.get_stats().total_requests == 0
        assert b._tokens == 3.0
        # After reset we should be able to consume 3 tokens again
        assert b.try_consume() is True
        assert b.try_consume() is True
        assert b.try_consume() is True
        assert b.try_consume() is False

    def test_str_representation(self) -> None:
        cfg = TokenBucketConfig(refill_rate=1.0, capacity=10.0)
        b = TokenBucket(cfg)
        s = str(b)
        assert "TokenBucket" in s
        assert "tokens=" in s
        assert "rate=" in s


class TestTokenBucketFactory:
    def test_create_token_bucket(self) -> None:
        b = create_token_bucket(refill_rate=2.0, capacity=8.0)
        assert isinstance(b, TokenBucket)
        assert b.config.refill_rate == 2.0
        assert b.config.capacity == 8.0

    def test_strict_token_bucket_disables_burst(self) -> None:
        b = create_strict_token_bucket(refill_rate=1.0, capacity=5.0)
        assert b.config.allow_burst is False
        assert b.config.burst_multiplier == 1.0

    def test_burst_token_bucket_allows_burst(self) -> None:
        b = create_burst_token_bucket(
            refill_rate=1.0, capacity=5.0, burst_multiplier=3.0
        )
        assert b.config.allow_burst is True
        assert b.config.burst_multiplier == 3.0
