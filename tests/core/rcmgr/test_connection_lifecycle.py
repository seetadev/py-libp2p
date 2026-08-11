"""
Tests for the rcmgr connection_lifecycle module.
"""

from __future__ import annotations

import pytest
import multiaddr

from libp2p.peer.id import ID
from libp2p.rcmgr.connection_limits import ConnectionLimits
from libp2p.rcmgr.connection_lifecycle import (
    ConnectionLifecycleManager,
    ConnectionLimitKind,
)
from libp2p.rcmgr.connection_tracker import ConnectionTracker
from libp2p.rcmgr.exceptions import ResourceLimitExceeded


def _peer(seed: int) -> ID:
    return ID(seed.to_bytes(32, "big"))


def _tcp(addr: str = "1.2.3.4", port: int = 4001) -> multiaddr.Multiaddr:
    return multiaddr.Multiaddr(f"/ip4/{addr}/tcp/{port}")


class TestConnectionLimitKind:
    def test_constants(self) -> None:
        assert ConnectionLimitKind.PENDING_INBOUND == "pending_inbound"
        assert ConnectionLimitKind.PENDING_OUTBOUND == "pending_outbound"
        assert ConnectionLimitKind.ESTABLISHED_INBOUND == "established_inbound"
        assert ConnectionLimitKind.ESTABLISHED_OUTBOUND == "established_outbound"
        assert ConnectionLimitKind.ESTABLISHED_PER_PEER == "established_per_peer"
        assert ConnectionLimitKind.ESTABLISHED_TOTAL == "established_total"


class TestConnectionLifecyclePendingInbound:
    async def test_adds_pending_inbound(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        await mgr.handle_pending_inbound_connection(
            "c1", _tcp("0.0.0.0"), _tcp("1.2.3.4"), _peer(1)
        )
        assert "c1" in ct.pending_inbound

    async def test_bypass_skips_limit_check(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct, ConnectionLimits(max_pending_inbound=0)
        )
        p = _peer(1)
        ct.add_bypass_peer(p)
        await mgr.handle_pending_inbound_connection(
            "c1", _tcp("0.0.0.0"), _tcp(), p
        )
        assert "c1" in ct.pending_inbound

    async def test_pending_inbound_limit_exceeded(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct, ConnectionLimits(max_pending_inbound=1)
        )
        await mgr.handle_pending_inbound_connection(
            "c1", _tcp("0.0.0.0"), _tcp(), _peer(1)
        )
        with pytest.raises(ResourceLimitExceeded):
            await mgr.handle_pending_inbound_connection(
                "c2", _tcp("0.0.0.0"), _tcp("5.6.7.8"), _peer(2)
            )


class TestConnectionLifecycleEstablishedInbound:
    async def test_moves_to_established_inbound(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        await mgr.handle_established_inbound_connection(
            "c1", p, _tcp("0.0.0.0"), _tcp()
        )
        assert "c1" in ct.established_inbound
        assert "c1" not in ct.pending_inbound

    async def test_bypass_skips_established_limit_check(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct,
            ConnectionLimits(
                max_established_inbound=0,
                max_established_total=0,
                max_established_per_peer=0,
            ),
        )
        p = _peer(1)
        ct.add_bypass_peer(p)
        ct.add_pending_inbound("c1", p)
        await mgr.handle_established_inbound_connection(
            "c1", p, _tcp("0.0.0.0"), _tcp()
        )
        assert "c1" in ct.established_inbound

    async def test_per_peer_limit_exceeded(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct, ConnectionLimits(max_established_per_peer=1)
        )
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        await mgr.handle_established_inbound_connection(
            "c1", p, _tcp("0.0.0.0"), _tcp()
        )
        ct.add_pending_inbound("c2", p)
        with pytest.raises(ResourceLimitExceeded):
            await mgr.handle_established_inbound_connection(
                "c2", p, _tcp("0.0.0.0"), _tcp()
            )


class TestConnectionLifecyclePendingOutbound:
    async def test_adds_pending_outbound(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        await mgr.handle_pending_outbound_connection(
            "c1", _peer(1), [_tcp()], "dialer"
        )
        assert "c1" in ct.pending_outbound

    async def test_bypass_skips_limit_check(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct, ConnectionLimits(max_pending_outbound=0)
        )
        p = _peer(1)
        ct.add_bypass_peer(p)
        await mgr.handle_pending_outbound_connection(
            "c1", p, [_tcp()], "dialer"
        )
        assert "c1" in ct.pending_outbound

    async def test_pending_outbound_limit_exceeded(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct, ConnectionLimits(max_pending_outbound=1)
        )
        await mgr.handle_pending_outbound_connection(
            "c1", _peer(1), [_tcp()], "dialer"
        )
        with pytest.raises(ResourceLimitExceeded):
            await mgr.handle_pending_outbound_connection(
                "c2", _peer(2), [_tcp("5.6.7.8")], "dialer"
            )


class TestConnectionLifecycleEstablishedOutbound:
    async def test_moves_to_established_outbound(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        p = _peer(1)
        ct.add_pending_outbound("c1", p)
        await mgr.handle_established_outbound_connection(
            "c1", p, _tcp("0.0.0.0"), "dialer"
        )
        assert "c1" in ct.established_outbound
        assert "c1" not in ct.pending_outbound

    async def test_bypass_skips_established_outbound_limit(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct,
            ConnectionLimits(
                max_established_outbound=0,
                max_established_total=0,
                max_established_per_peer=0,
            ),
        )
        p = _peer(1)
        ct.add_bypass_peer(p)
        ct.add_pending_outbound("c1", p)
        await mgr.handle_established_outbound_connection(
            "c1", p, _tcp("0.0.0.0"), "dialer"
        )
        assert "c1" in ct.established_outbound

    async def test_total_limit_exceeded(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(
            ct, ConnectionLimits(max_established_total=1)
        )
        p1, p2 = _peer(1), _peer(2)
        ct.add_pending_inbound("c1", p1)
        await mgr.handle_established_inbound_connection(
            "c1", p1, _tcp("0.0.0.0"), _tcp()
        )
        ct.add_pending_outbound("c2", p2)
        with pytest.raises(ResourceLimitExceeded):
            await mgr.handle_established_outbound_connection(
                "c2", p2, _tcp("0.0.0.0"), "dialer"
            )


class TestConnectionLifecycleClosed:
    async def test_closed_removes_connection(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        await mgr.handle_connection_closed("c1", p)
        assert "c1" not in ct.pending_inbound

    async def test_closed_unknown_id_does_not_raise(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        await mgr.handle_connection_closed("missing")


class TestConnectionLifecycleAccessors:
    def test_get_connection_stats(self) -> None:
        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        stats = mgr.get_connection_stats()
        assert "current_pending_inbound" in stats

    def test_get_limits_summary(self) -> None:
        mgr = ConnectionLifecycleManager(
            ConnectionTracker(), ConnectionLimits(max_pending_inbound=4)
        )
        summary = mgr.get_limits_summary()
        assert summary["max_pending_inbound"] == 4


class TestConnectionLifecycleDunder:
    def test_eq_same_tracker_and_limits(self) -> None:
        ct = ConnectionTracker()
        limits = ConnectionLimits()
        m1 = ConnectionLifecycleManager(ct, limits)
        m2 = ConnectionLifecycleManager(ct, limits)
        assert m1 == m2

    def test_eq_different_tracker(self) -> None:
        m1 = ConnectionLifecycleManager(ConnectionTracker(), ConnectionLimits())
        m2 = ConnectionLifecycleManager(ConnectionTracker(), ConnectionLimits())
        assert m1 != m2

    def test_eq_non_manager(self) -> None:
        m = ConnectionLifecycleManager(ConnectionTracker(), ConnectionLimits())
        assert (m == "not a manager") is False

    def test_hash_distinct_for_distinct_trackers(self) -> None:
        m1 = ConnectionLifecycleManager(ConnectionTracker(), ConnectionLimits())
        m2 = ConnectionLifecycleManager(ConnectionTracker(), ConnectionLimits())
        assert hash(m1) != hash(m2)

    def test_str(self) -> None:
        m = ConnectionLifecycleManager(ConnectionTracker(), ConnectionLimits())
        s = str(m)
        assert "ConnectionLifecycleManager" in s

    def test_deepcopy_preserves_state(self) -> None:
        import copy

        ct = ConnectionTracker()
        mgr = ConnectionLifecycleManager(ct, ConnectionLimits())
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        copy_mgr = copy.deepcopy(mgr)
        assert "c1" in copy_mgr.tracker.pending_inbound
        # mutating the copy must not affect the original
        copy_mgr.tracker.pending_inbound.discard("c1")
        assert "c1" in ct.pending_inbound
