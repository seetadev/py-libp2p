"""
Tests for the rcmgr graceful_degradation module.
"""

from __future__ import annotations

import pytest

from libp2p.rcmgr.graceful_degradation import GracefulDegradation
from libp2p.rcmgr.manager import ResourceLimits, ResourceManager


@pytest.fixture
def rm() -> ResourceManager:
    return ResourceManager(
        limits=ResourceLimits(
            max_connections=100,
            max_memory_mb=128,
            max_streams=200,
        ),
        enable_graceful_degradation=False,
    )


class TestGracefulDegradationInit:
    def test_stores_original_limits(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm)
        assert gd.original_limits is not None
        assert gd.original_limits.max_connections == 100
        assert gd.original_limits.max_memory_bytes == 128 * 1024 * 1024
        assert gd.original_limits.max_streams == 200
        assert gd.degradation_level == 0

    def test_custom_parameters(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(
            rm, max_degradation_levels=3, degradation_factor=0.1
        )
        assert gd.max_degradation_levels == 3
        assert gd.degradation_factor == 0.1


class TestGracefulDegradationConnections:
    def test_degrade_connections(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.2)
        result = gd.handle_resource_exhaustion("connections")
        assert result is True
        assert gd.degradation_level == 1
        # 100 * (1 - 0.2) = 80
        assert rm.limits.max_connections == 80

    def test_degrade_connections_repeated(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.2)
        gd.handle_resource_exhaustion("connections")
        # Level 1: 100 * 0.8 = 80
        gd.handle_resource_exhaustion("connections")
        # Level 2: 100 * 0.6 = 60
        assert gd.degradation_level == 2
        assert rm.limits.max_connections == 60

    def test_min_connection_floor(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(
            rm, max_degradation_levels=5, degradation_factor=0.8
        )
        # Level 1: 100 * 0.2 = 20
        gd.handle_resource_exhaustion("connections")
        # Level 2: 100 * -0.6 -> clamped to 1
        gd.handle_resource_exhaustion("connections")
        assert rm.limits.max_connections == 1


class TestGracefulDegradationMemory:
    def test_degrade_memory(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.5)
        result = gd.handle_resource_exhaustion("memory")
        assert result is True
        # original 128MB, * 0.5 = 64MB
        assert rm.limits.max_memory_bytes == 64 * 1024 * 1024

    def test_min_memory_floor(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(
            rm, max_degradation_levels=5, degradation_factor=0.99
        )
        gd.handle_resource_exhaustion("memory")
        gd.handle_resource_exhaustion("memory")
        # clamped to 1MB minimum
        assert rm.limits.max_memory_bytes >= 1024 * 1024


class TestGracefulDegradationStreams:
    def test_degrade_streams(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.25)
        gd.handle_resource_exhaustion("streams")
        # 200 * 0.75 = 150
        assert rm.limits.max_streams == 150


class TestGracefulDegradationLimits:
    def test_unknown_resource_returns_false(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm)
        assert gd.handle_resource_exhaustion("unknown") is False
        # Unknown resource still increments the level but applies no change
        assert gd.degradation_level == 1
        # And the actual limits are untouched
        assert rm.limits.max_connections == 100
        assert rm.limits.max_memory_bytes == 128 * 1024 * 1024
        assert rm.limits.max_streams == 200

    def test_max_level_returns_false(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=2, degradation_factor=0.2)
        assert gd.handle_resource_exhaustion("connections") is True
        assert gd.handle_resource_exhaustion("connections") is True
        # 3rd call exceeds max level
        assert gd.handle_resource_exhaustion("connections") is False
        assert gd.degradation_level == 2


class TestGracefulDegradationRecovery:
    def test_recover_at_zero_level_is_noop(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm)
        assert gd.recover() is True
        assert gd.degradation_level == 0

    def test_recover_lowers_level(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.2)
        gd.handle_resource_exhaustion("connections")
        gd.handle_resource_exhaustion("connections")
        assert gd.degradation_level == 2
        # stats will show low usage (0 / current_limit), so recovery is possible
        assert gd.recover() is True
        assert gd.degradation_level == 1

    def test_recover_fails_under_high_load(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.2)
        gd.handle_resource_exhaustion("connections")
        # artificially push connection usage above 80% of the current limit
        rm._current_connections = int(rm.limits.max_connections * 0.9)
        assert gd.recover() is False
        assert gd.degradation_level == 1


class TestGracefulDegradationReset:
    def test_reset_restores_original(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.5)
        gd.handle_resource_exhaustion("connections")
        gd.handle_resource_exhaustion("memory")
        assert rm.limits.max_connections != 100
        assert rm.limits.max_memory_bytes != 128 * 1024 * 1024
        gd.reset()
        assert rm.limits.max_connections == 100
        assert rm.limits.max_memory_bytes == 128 * 1024 * 1024
        assert rm.limits.max_streams == 200
        assert gd.degradation_level == 0

    def test_reset_safe_when_no_limits_stored(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm)
        gd.original_limits = None
        gd.reset()  # must not raise
        assert gd.degradation_level == 0


class TestGracefulDegradationStats:
    def test_get_stats_shape(self, rm: ResourceManager) -> None:
        gd = GracefulDegradation(rm, max_degradation_levels=5, degradation_factor=0.2)
        stats = gd.get_stats()
        assert stats["degradation_level"] == 0
        assert stats["max_degradation_levels"] == 5
        assert stats["degradation_factor"] == 0.2
        assert "current_limits" in stats
        assert "original_limits" in stats
        assert stats["current_limits"]["max_connections"] == 100
        assert stats["original_limits"]["max_connections"] == 100
