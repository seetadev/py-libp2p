"""
Tests for the rcmgr memory_limits module.
"""

from __future__ import annotations

import pytest

from libp2p.rcmgr.exceptions import ResourceLimitExceeded
from libp2p.rcmgr.memory_limits import (
    MemoryConnectionLimits,
    new_memory_connection_limits,
    new_memory_connection_limits_with_bytes,
    new_memory_connection_limits_with_defaults,
    new_memory_connection_limits_with_percent,
)
from libp2p.rcmgr.memory_stats import MemoryStats, MemoryStatsCache


class _FakeCache:
    """MemoryStatsCache stand-in returning caller-controlled stats."""

    def __init__(self, stats: MemoryStats) -> None:
        self._stats = stats
        self.force_refresh_called = 0

    def get_memory_stats(self, force_refresh: bool = False) -> MemoryStats:
        if force_refresh:
            self.force_refresh_called += 1
        return self._stats

    def get_memory_summary(self, force_refresh: bool = False) -> dict:
        return {
            "process_memory_bytes": self._stats.process_memory_bytes,
            "process_memory_percent": self._stats.process_memory_percent,
            "system_memory_total": self._stats.system_memory_total,
            "system_memory_available": self._stats.system_memory_available,
            "system_memory_percent": self._stats.system_memory_percent,
        }


def _stats(
    proc_bytes: int = 100 * 1024 * 1024,
    proc_pct: float = 10.0,
    sys_total: int = 1024 * 1024 * 1024,
    sys_avail: int = 512 * 1024 * 1024,
    sys_pct: float = 50.0,
) -> MemoryStats:
    return MemoryStats(
        process_memory_bytes=proc_bytes,
        process_memory_percent=proc_pct,
        system_memory_total=sys_total,
        system_memory_available=sys_avail,
        system_memory_percent=sys_pct,
        timestamp=0.0,
    )


class TestMemoryConnectionLimitsBuilder:
    def test_defaults(self) -> None:
        limits = new_memory_connection_limits()
        assert limits.max_process_memory_bytes is None
        assert limits.max_process_memory_percent is None
        assert limits.max_system_memory_percent is None
        assert limits.memory_stats_cache is not None

    def test_with_bytes(self) -> None:
        limits = new_memory_connection_limits_with_bytes(2 * 1024 * 1024 * 1024)
        assert limits.max_process_memory_bytes == 2 * 1024 * 1024 * 1024

    def test_with_percent(self) -> None:
        limits = new_memory_connection_limits_with_percent(75.0)
        assert limits.max_process_memory_percent == 75.0

    def test_with_defaults_factory(self) -> None:
        limits = new_memory_connection_limits_with_defaults()
        assert limits.max_process_memory_percent == 80.0
        assert limits.max_system_memory_percent == 90.0


class TestMemoryConnectionLimitsBuilderMethods:
    def test_fluent_builders_return_self(self) -> None:
        cache = MemoryStatsCache(cache_duration=1.0)
        limits = MemoryConnectionLimits()
        assert limits.with_max_process_memory_bytes(100) is limits
        assert limits.with_max_process_memory_percent(50.0) is limits
        assert limits.with_max_system_memory_percent(80.0) is limits
        assert limits.with_memory_stats_cache(cache) is limits
        assert limits.max_process_memory_bytes == 100
        assert limits.max_process_memory_percent == 50.0
        assert limits.max_system_memory_percent == 80.0
        assert limits.memory_stats_cache is cache

    @pytest.mark.parametrize("bad", [-0.1, 100.1, 200.0])
    def test_invalid_process_percent(self, bad: float) -> None:
        with pytest.raises(ValueError):
            MemoryConnectionLimits().with_max_process_memory_percent(bad)

    @pytest.mark.parametrize("bad", [-0.1, 100.1, 200.0])
    def test_invalid_system_percent(self, bad: float) -> None:
        with pytest.raises(ValueError):
            MemoryConnectionLimits().with_max_system_memory_percent(bad)


class TestMemoryConnectionLimitsCheck:
    def test_no_limits_configured_is_noop(self) -> None:
        limits = MemoryConnectionLimits(memory_stats_cache=_FakeCache(_stats()))
        limits.check_memory_limits()  # must not raise

    def test_process_bytes_within_limit(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_bytes=200 * 1024 * 1024,
            memory_stats_cache=_FakeCache(_stats(proc_bytes=100 * 1024 * 1024)),
        )
        limits.check_memory_limits()

    def test_process_bytes_exceeded(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_bytes=50 * 1024 * 1024,
            memory_stats_cache=_FakeCache(_stats(proc_bytes=100 * 1024 * 1024)),
        )
        with pytest.raises(ResourceLimitExceeded):
            limits.check_memory_limits()

    def test_process_percent_within_limit(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_percent=50.0,
            memory_stats_cache=_FakeCache(_stats(proc_pct=20.0)),
        )
        limits.check_memory_limits()

    def test_process_percent_exceeded(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_percent=10.0,
            memory_stats_cache=_FakeCache(_stats(proc_pct=20.0)),
        )
        with pytest.raises(ResourceLimitExceeded):
            limits.check_memory_limits()

    def test_system_percent_exceeded(self) -> None:
        limits = MemoryConnectionLimits(
            max_system_memory_percent=50.0,
            memory_stats_cache=_FakeCache(_stats(sys_pct=80.0)),
        )
        with pytest.raises(ResourceLimitExceeded):
            limits.check_memory_limits()

    def test_cache_failure_is_swallowed(self) -> None:
        class _BrokenCache(_FakeCache):
            def get_memory_stats(self, force_refresh: bool = False) -> MemoryStats:
                raise OSError("psutil broken")

        limits = MemoryConnectionLimits(
            max_process_memory_bytes=100,
            memory_stats_cache=_BrokenCache(_stats()),
        )
        # Monitoring failure must not raise (matches Rust semantics)
        limits.check_memory_limits()

    def test_get_current_memory_stats_raises_without_cache(self) -> None:
        # Bypass __post_init__ so we can construct an instance with no cache
        limits = MemoryConnectionLimits.__new__(MemoryConnectionLimits)
        limits.max_process_memory_bytes = None
        limits.max_process_memory_percent = None
        limits.max_system_memory_percent = None
        limits.memory_stats_cache = None
        with pytest.raises(RuntimeError):
            limits.get_current_memory_stats()


class TestMemoryConnectionLimitsSummary:
    def test_limits_summary(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_bytes=100,
            max_process_memory_percent=50.0,
        )
        s = limits.get_limits_summary()
        assert s["max_process_memory_bytes"] == 100
        assert s["max_process_memory_percent"] == 50.0
        assert s["has_limits_configured"] is True

    def test_memory_summary_without_cache(self) -> None:
        # Bypass __post_init__ so we can construct an instance with no cache
        limits = MemoryConnectionLimits.__new__(MemoryConnectionLimits)
        limits.max_process_memory_bytes = None
        limits.max_process_memory_percent = None
        limits.max_system_memory_percent = None
        limits.memory_stats_cache = None
        s = limits.get_memory_summary()
        # No current key when cache is missing
        assert "current" not in s
        assert "has_limits_configured" in s

    def test_memory_summary_includes_current(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_bytes=100, memory_stats_cache=_FakeCache(_stats())
        )
        s = limits.get_memory_summary()
        assert "current" in s
        assert s["current"]["process_memory_bytes"] == 100 * 1024 * 1024

    def test_str_with_no_limits(self) -> None:
        s = str(MemoryConnectionLimits(memory_stats_cache=None))
        assert s == "MemoryConnectionLimits(no_limits)"

    def test_str_with_limits(self) -> None:
        limits = MemoryConnectionLimits(
            max_process_memory_bytes=100,
            max_process_memory_percent=10.0,
            max_system_memory_percent=90.0,
        )
        s = str(limits)
        assert "process_bytes=100" in s
        assert "process_percent=10.0%" in s
        assert "system_percent=90.0%" in s


class TestMemoryConnectionLimitsDunder:
    def test_eq_same_values(self) -> None:
        a = MemoryConnectionLimits(
            max_process_memory_bytes=100, max_process_memory_percent=50.0
        )
        b = MemoryConnectionLimits(
            max_process_memory_bytes=100, max_process_memory_percent=50.0
        )
        assert a == b
        assert hash(a) == hash(b)

    def test_eq_different_values(self) -> None:
        a = MemoryConnectionLimits(max_process_memory_bytes=100)
        b = MemoryConnectionLimits(max_process_memory_bytes=200)
        assert a != b

    def test_eq_non_mc_limits(self) -> None:
        a = MemoryConnectionLimits()
        assert (a == "foo") is False

    def test_deepcopy_does_not_share_cache(self) -> None:
        import copy

        cache = MemoryStatsCache()
        a = MemoryConnectionLimits(
            max_process_memory_bytes=100, memory_stats_cache=cache
        )
        b = copy.deepcopy(a)
        assert b.memory_stats_cache is not cache
        assert b.max_process_memory_bytes == 100
