"""
Tests for the rcmgr protocol_rate_limiter module.
"""

from __future__ import annotations

import pytest

from libp2p.peer.id import ID
from libp2p.rcmgr.protocol_rate_limiter import (
    ProtocolRateLimitConfig,
    ProtocolRateLimiter,
    create_burst_protocol_rate_limiter,
    create_protocol_rate_limiter,
    create_strict_protocol_rate_limiter,
)
from libp2p.rcmgr.rate_limiter import RateLimitScope


def _peer(seed: int) -> ID:
    return ID(seed.to_bytes(32, "big"))


def _valid_config(**overrides: object) -> ProtocolRateLimitConfig:
    cfg: dict[str, object] = {
        "protocol_name": "/test/proto/1.0.0",
        "refill_rate": 1000.0,
        "capacity": 100.0,
    }
    cfg.update(overrides)
    return ProtocolRateLimitConfig(**cfg)  # type: ignore[arg-type]


class TestProtocolRateLimitConfig:
    def test_defaults(self) -> None:
        cfg = _valid_config()
        assert cfg.protocol_name == "/test/proto/1.0.0"
        assert cfg.refill_rate == 1000.0
        assert cfg.capacity == 100.0
        assert cfg.max_concurrent_requests == 10

    def test_empty_protocol_name_raises(self) -> None:
        with pytest.raises(ValueError):
            ProtocolRateLimitConfig(protocol_name="", refill_rate=1.0, capacity=1.0)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"refill_rate": 0},
            {"capacity": 0},
            {"initial_tokens": -1},
            {"initial_tokens": 1000, "capacity": 10},
            {"burst_multiplier": 0.5},
            {"time_window_seconds": 0},
            {"min_interval_seconds": 0},
            {"max_history_size": 0},
            {"max_peers": 0},
            {"max_connections": 0},
            {"max_concurrent_requests": 0},
            {"request_timeout_seconds": 0},
            {"backoff_factor": 0.5},
        ],
    )
    def test_invalid_config(self, kwargs: dict) -> None:
        with pytest.raises(ValueError):
            _valid_config(**kwargs)


class TestProtocolRateLimiterAllow:
    def test_allows_under_capacity(self) -> None:
        cfg = _valid_config(
            refill_rate=1.0, capacity=5.0, initial_tokens=5.0
        )
        rl = ProtocolRateLimiter(cfg)
        for _ in range(5):
            assert rl.try_allow_request() is True

    def test_denies_over_capacity(self) -> None:
        cfg = _valid_config(
            refill_rate=0.001, capacity=2.0, initial_tokens=2.0
        )
        rl = ProtocolRateLimiter(cfg)
        assert rl.try_allow_request() is True
        assert rl.try_allow_request() is True
        assert rl.try_allow_request() is False

    def test_per_peer_scope_isolates_entities(self) -> None:
        cfg = _valid_config(
            refill_rate=0.001,
            capacity=1.0,
            initial_tokens=1.0,
            scope=RateLimitScope.PER_PEER,
        )
        rl = ProtocolRateLimiter(cfg)
        assert rl.try_allow_request(peer_id=_peer(1)) is True
        assert rl.try_allow_request(peer_id=_peer(1)) is False
        # Different peer has its own bucket
        assert rl.try_allow_request(peer_id=_peer(2)) is True

    def test_per_connection_scope_isolates_entities(self) -> None:
        cfg = _valid_config(
            refill_rate=0.001,
            capacity=1.0,
            initial_tokens=1.0,
            scope=RateLimitScope.PER_CONNECTION,
        )
        rl = ProtocolRateLimiter(cfg)
        assert rl.try_allow_request(connection_id="c1") is True
        assert rl.try_allow_request(connection_id="c1") is False
        assert rl.try_allow_request(connection_id="c2") is True

    def test_global_scope_shares_state(self) -> None:
        cfg = _valid_config(
            refill_rate=0.001,
            capacity=1.0,
            initial_tokens=1.0,
            scope=RateLimitScope.GLOBAL,
        )
        rl = ProtocolRateLimiter(cfg)
        assert rl.try_allow_request(peer_id=_peer(1)) is True
        # Second peer must hit the same global bucket
        assert rl.try_allow_request(peer_id=_peer(2)) is False

    def test_allow_request_raises_when_denied(self) -> None:
        # No initial tokens, refill rate near zero, capacity tiny -> bucket
        # is empty so the very first request must be denied.
        cfg = _valid_config(
            refill_rate=0.0001,
            capacity=0.001,
        )
        rl = ProtocolRateLimiter(cfg)
        with pytest.raises(ValueError):
            rl.allow_request()

    def test_finish_request_decrements_concurrent(self) -> None:
        cfg = _valid_config(
            refill_rate=1.0,
            capacity=10.0,
            initial_tokens=10.0,
            max_concurrent_requests=10,
        )
        rl = ProtocolRateLimiter(cfg)
        rl.try_allow_request(peer_id=_peer(1))
        rl.try_allow_request(peer_id=_peer(1))
        stats = rl.get_stats(peer_id=_peer(1))
        assert stats.concurrent_requests == 2
        rl.finish_request(peer_id=_peer(1))
        stats = rl.get_stats(peer_id=_peer(1))
        assert stats.concurrent_requests == 1

    def test_concurrent_limit_triggers_backoff(self) -> None:
        cfg = _valid_config(
            refill_rate=1000.0,
            capacity=1000.0,
            initial_tokens=1000.0,
            max_concurrent_requests=1,
            request_timeout_seconds=10.0,
            backoff_factor=2.0,
        )
        rl = ProtocolRateLimiter(cfg)
        assert rl.try_allow_request(peer_id=_peer(1)) is True
        # Concurrent limit hit, so the next call should fail and start backoff
        assert rl.try_allow_request(peer_id=_peer(1)) is False
        # And any subsequent call during the backoff window must also fail
        assert rl.try_allow_request(peer_id=_peer(1)) is False
        stats = rl.get_stats(peer_id=_peer(1))
        assert stats.backoff_events >= 1


class TestProtocolRateLimiterStats:
    def test_get_stats_fields(self) -> None:
        cfg = _valid_config(initial_tokens=5.0)
        rl = ProtocolRateLimiter(cfg)
        rl.try_allow_request(peer_id=_peer(1))
        stats = rl.get_stats(peer_id=_peer(1))
        d = stats.to_dict()
        assert d["protocol_name"] == cfg.protocol_name
        assert d["total_requests"] >= 1
        assert d["allowed_requests"] >= 1
        assert d["max_concurrent_requests"] == cfg.max_concurrent_requests
        assert d["scope"] == cfg.scope.value

    def test_get_entity_stats(self) -> None:
        cfg = _valid_config(initial_tokens=5.0)
        rl = ProtocolRateLimiter(cfg)
        rl.try_allow_request(peer_id=_peer(1))
        info = rl.get_entity_stats(peer_id=_peer(1))
        assert info["protocol_name"] == cfg.protocol_name
        assert info["concurrent_requests"] == 1
        assert info["in_backoff"] is False

    def test_reset(self) -> None:
        cfg = _valid_config(initial_tokens=1.0)
        rl = ProtocolRateLimiter(cfg)
        rl.try_allow_request(peer_id=_peer(1))
        rl.try_allow_request(peer_id=_peer(1))
        rl.reset()
        stats = rl.get_stats(peer_id=_peer(1))
        assert stats.total_requests == 0
        assert stats.concurrent_requests == 0
        assert stats.backoff_events == 0


class TestProtocolRateLimiterFactory:
    def test_create_default(self) -> None:
        rl = create_protocol_rate_limiter("/x/1", refill_rate=10.0, capacity=5.0)
        assert isinstance(rl, ProtocolRateLimiter)
        assert rl.config.protocol_name == "/x/1"
        assert rl.config.refill_rate == 10.0
        assert rl.config.capacity == 5.0

    def test_strict_factory_disables_burst(self) -> None:
        rl = create_strict_protocol_rate_limiter("/x/1")
        assert rl.config.allow_burst is False
        assert rl.config.burst_multiplier == 1.0

    def test_burst_factory_allows_burst(self) -> None:
        rl = create_burst_protocol_rate_limiter(
            "/x/1", burst_multiplier=3.0
        )
        assert rl.config.allow_burst is True
        assert rl.config.burst_multiplier == 3.0

    def test_str(self) -> None:
        rl = create_protocol_rate_limiter("/x/1")
        s = str(rl)
        assert "ProtocolRateLimiter" in s
        assert "/x/1" in s
