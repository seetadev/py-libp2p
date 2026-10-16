"""
Tests for the rcmgr connection_tracker module.
"""

from __future__ import annotations

import pytest

from libp2p.peer.id import ID
from libp2p.rcmgr.connection_limits import ConnectionLimits
from libp2p.rcmgr.connection_tracker import ConnectionInfo, ConnectionTracker


def _peer(seed: int) -> ID:
    return ID(seed.to_bytes(32, "big"))


class TestConnectionInfo:
    def test_is_properties(self) -> None:
        info = ConnectionInfo(
            connection_id="c1",
            peer_id=_peer(1),
            direction="inbound",
            state="pending",
            created_at=0.0,
        )
        assert info.is_pending is True
        assert info.is_established is False
        assert info.is_inbound is True
        assert info.is_outbound is False

        info.state = "established"
        info.direction = "outbound"
        assert info.is_pending is False
        assert info.is_established is True
        assert info.is_inbound is False
        assert info.is_outbound is True


class TestConnectionTrackerBasics:
    def test_default_construction(self) -> None:
        ct = ConnectionTracker()
        assert ct.limits is not None
        assert ct.pending_inbound == set()
        assert ct.pending_outbound == set()
        assert ct.established_inbound == set()
        assert ct.established_outbound == set()
        assert ct.established_per_peer == {}
        assert ct.bypass_peers == set()

    def test_custom_limits(self) -> None:
        limits = ConnectionLimits(max_pending_inbound=4)
        ct = ConnectionTracker(limits=limits)
        assert ct.limits is limits


class TestConnectionTrackerPending:
    def test_add_pending_inbound(self) -> None:
        ct = ConnectionTracker()
        ct.add_pending_inbound("c1", _peer(1))
        assert "c1" in ct.pending_inbound
        assert ct.get_connection_count("pending_inbound") == 1
        assert ct._stats["peak_pending_inbound"] == 1

    def test_add_pending_outbound(self) -> None:
        ct = ConnectionTracker()
        ct.add_pending_outbound("c1", _peer(1))
        assert "c1" in ct.pending_outbound
        assert ct.get_connection_count("pending_outbound") == 1
        assert ct._stats["peak_pending_outbound"] == 1

    def test_peak_tracking(self) -> None:
        ct = ConnectionTracker()
        ct.add_pending_inbound("c1", _peer(1))
        ct.add_pending_inbound("c2", _peer(1))
        ct.remove_connection("c1")
        assert ct._stats["peak_pending_inbound"] == 2
        assert ct.get_connection_count("pending_inbound") == 1


class TestConnectionTrackerEstablished:
    def test_move_to_established_inbound(self) -> None:
        ct = ConnectionTracker()
        peer = _peer(5)
        ct.add_pending_inbound("c1", peer)
        ct.move_to_established_inbound("c1", peer)
        assert "c1" not in ct.pending_inbound
        assert "c1" in ct.established_inbound
        assert "c1" in ct.established_per_peer[peer]
        info = ct.get_connection_info("c1")
        assert info is not None
        assert info.state == "established"
        assert info.peer_id == peer
        assert info.established_at is not None
        assert ct._stats["total_connections_established"] == 1
        assert ct._stats["peak_established_inbound"] == 1

    def test_move_to_established_outbound(self) -> None:
        ct = ConnectionTracker()
        peer = _peer(6)
        ct.add_pending_outbound("c1", peer)
        ct.move_to_established_outbound("c1", peer)
        assert "c1" in ct.established_outbound
        assert "c1" in ct.established_per_peer[peer]
        assert ct._stats["peak_established_outbound"] == 1

    def test_established_total_count(self) -> None:
        ct = ConnectionTracker()
        p1, p2 = _peer(1), _peer(2)
        ct.add_pending_inbound("c1", p1)
        ct.add_pending_inbound("c2", p2)
        ct.move_to_established_inbound("c1", p1)
        ct.move_to_established_inbound("c2", p2)
        assert ct.get_connection_count("established_total") == 2


class TestConnectionTrackerRemove:
    def test_remove_connection_clears_all_states(self) -> None:
        ct = ConnectionTracker()
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        ct.move_to_established_inbound("c1", p)
        assert "c1" in ct.established_inbound
        ct.remove_connection("c1", p)
        assert "c1" not in ct.established_inbound
        assert "c1" not in ct.pending_inbound
        assert ct.get_connection_info("c1") is None
        assert ct._stats["total_connections_closed"] == 1

    def test_remove_connection_clears_per_peer_bucket(self) -> None:
        ct = ConnectionTracker()
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        ct.move_to_established_inbound("c1", p)
        ct.remove_connection("c1", p)
        assert p not in ct.established_per_peer

    def test_remove_unknown_connection_is_noop(self) -> None:
        ct = ConnectionTracker()
        ct.remove_connection("nonexistent")
        assert ct._stats["total_connections_closed"] == 1


class TestConnectionTrackerPeerCounts:
    def test_peer_connection_count(self) -> None:
        ct = ConnectionTracker()
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        ct.move_to_established_inbound("c1", p)
        ct.add_pending_inbound("c2", p)
        ct.move_to_established_inbound("c2", p)
        assert ct.get_peer_connection_count(p) == 2

    def test_peer_connection_count_unknown(self) -> None:
        ct = ConnectionTracker()
        assert ct.get_peer_connection_count(_peer(99)) == 0


class TestConnectionTrackerBypass:
    def test_bypass_add_and_check(self) -> None:
        ct = ConnectionTracker()
        p = _peer(1)
        assert ct.is_bypassed(p) is False
        ct.add_bypass_peer(p)
        assert ct.is_bypassed(p) is True
        ct.remove_bypass_peer(p)
        assert ct.is_bypassed(p) is False

    def test_bypass_is_idempotent(self) -> None:
        ct = ConnectionTracker()
        p = _peer(1)
        ct.add_bypass_peer(p)
        ct.add_bypass_peer(p)
        ct.remove_bypass_peer(p)
        # Already removed, must not raise
        ct.remove_bypass_peer(p)


class TestConnectionTrackerGetCount:
    def test_unknown_kind_raises(self) -> None:
        ct = ConnectionTracker()
        with pytest.raises(ValueError):
            ct.get_connection_count("nope")


class TestConnectionTrackerStats:
    def test_get_stats_keys(self) -> None:
        ct = ConnectionTracker()
        stats = ct.get_stats()
        for key in (
            "total_connections_created",
            "total_connections_established",
            "total_connections_closed",
            "peak_pending_inbound",
            "peak_pending_outbound",
            "peak_established_inbound",
            "peak_established_outbound",
            "current_pending_inbound",
            "current_pending_outbound",
            "current_established_inbound",
            "current_established_outbound",
            "current_established_total",
            "current_peers_with_connections",
            "bypass_peers_count",
        ):
            assert key in stats

    def test_clear(self) -> None:
        ct = ConnectionTracker()
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        ct.add_bypass_peer(p)
        ct.clear()
        assert ct.pending_inbound == set()
        assert ct.bypass_peers == set()
        assert ct.established_per_peer == {}


class TestConnectionTrackerDunder:
    def test_eq_same_state(self) -> None:
        a = ConnectionTracker()
        b = ConnectionTracker()
        assert a == b
        a.add_pending_inbound("c1", _peer(1))
        assert a != b

    def test_eq_different_type(self) -> None:
        a = ConnectionTracker()
        assert (a == "foo") is False

    def test_copy_and_deepcopy(self) -> None:
        import copy

        ct = ConnectionTracker()
        p = _peer(1)
        ct.add_pending_inbound("c1", p)
        ct.move_to_established_inbound("c1", p)
        ct.add_bypass_peer(p)

        shallow = copy.copy(ct)
        assert shallow == ct
        shallow.add_pending_inbound("c2", p)
        assert shallow != ct

        deep = copy.deepcopy(ct)
        assert deep == ct

    def test_str_contains_counts(self) -> None:
        ct = ConnectionTracker()
        s = str(ct)
        assert "ConnectionTracker" in s
        assert "pending_inbound=0" in s
