"""
Tests for the rcmgr allowlist module.
"""

from __future__ import annotations

from multiaddr import Multiaddr

from libp2p.peer.id import ID
from libp2p.rcmgr.allowlist import (
    Allowlist,
    AllowlistConfig,
    new_allowlist,
    new_allowlist_with_config,
)


def _peer(seed: int) -> ID:
    return ID(seed.to_bytes(32, "big"))


class TestAllowlistConfig:
    def test_defaults_are_empty(self) -> None:
        cfg = AllowlistConfig()
        assert cfg.peers == set()
        assert cfg.multiaddrs == set()
        assert cfg.peer_multiaddrs == set()


class TestAllowlistBasics:
    def test_new_allowlist_is_empty(self) -> None:
        a = new_allowlist()
        assert a.is_empty() is True
        assert len(a) == 0

    def test_new_with_config_copies_sets(self) -> None:
        p = _peer(1)
        cfg = AllowlistConfig(peers={p}, multiaddrs={"/ip4/1.2.3.4"})
        a = new_allowlist_with_config(cfg)
        # mutation of original config should not affect the allowlist
        cfg.peers.add(_peer(2))
        assert _peer(2) not in a.peers
        assert p in a.peers
        assert "/ip4/1.2.3.4" in a.multiaddrs

    def test_add_remove_peer(self) -> None:
        a = Allowlist()
        p1, p2 = _peer(1), _peer(2)
        a.add_peer(p1)
        a.add_peer(p1)  # idempotent
        assert a.allowed_peer(p1) is True
        assert a.allowed_peer(p2) is False
        a.remove_peer(p1)
        assert a.allowed_peer(p1) is False
        a.remove_peer(p1)  # no error on missing

    def test_add_remove_multiaddr_string_and_object(self) -> None:
        a = Allowlist()
        ma_str = "/ip4/1.2.3.4/tcp/4001"
        ma_obj = Multiaddr(ma_str)
        a.add_multiaddr(ma_str)
        a.add_multiaddr(ma_obj)
        assert a.allowed_multiaddr(ma_str) is True
        assert a.allowed_multiaddr(ma_obj) is True
        a.remove_multiaddr(ma_obj)
        assert a.allowed_multiaddr(ma_str) is False

    def test_add_remove_peer_multiaddr(self) -> None:
        a = Allowlist()
        p = _peer(7)
        ma = "/ip4/5.6.7.8"
        a.add_peer_multiaddr(p, ma)
        assert a.allowed_peer_and_multiaddr(p, ma) is True
        assert a.allowed_peer_and_multiaddr(_peer(8), ma) is False
        a.remove_peer_multiaddr(p, ma)
        assert a.allowed_peer_and_multiaddr(p, ma) is False


class TestAllowlistLookup:
    def test_allowed_multiaddr_no_match_returns_false(self) -> None:
        a = Allowlist()
        assert a.allowed_multiaddr("/ip4/9.9.9.9") is False

    def test_allowed_alias_matches_multiaddr(self) -> None:
        a = Allowlist()
        a.add_multiaddr("/ip4/1.1.1.1")
        assert a.allowed("/ip4/1.1.1.1") is True
        assert a.allowed("/ip4/1.1.1.2") is False

    def test_peer_and_multiaddr_priority(self) -> None:
        """Peer-multiaddr entry, peer-only entry, and multiaddr-only entry all match."""
        a = Allowlist()
        p = _peer(3)
        ma = "/ip4/4.4.4.4"
        other_ma = "/ip4/4.4.4.5"

        # 1. specific (peer, multiaddr) entry
        a.add_peer_multiaddr(p, ma)
        assert a.allowed_peer_and_multiaddr(p, ma) is True

        # 2. peer-only entry matches for any multiaddr
        a.add_peer(_peer(9))
        assert a.allowed_peer_and_multiaddr(_peer(9), other_ma) is True

        # 3. multiaddr-only entry matches for any peer
        a.add_multiaddr(other_ma)
        assert a.allowed_peer_and_multiaddr(_peer(99), other_ma) is True

    def test_get_allowed_returns_copies(self) -> None:
        a = Allowlist()
        a.add_peer(_peer(1))
        a.add_multiaddr("/ip4/1.1.1.1")
        peers = a.get_allowed_peers()
        peers.add(_peer(2))  # mutation should not affect allowlist
        assert _peer(2) not in a.peers
        mas = a.get_allowed_multiaddrs()
        mas.add("/ip4/2.2.2.2")
        assert "/ip4/2.2.2.2" not in a.multiaddrs

    def test_clear_empties_everything(self) -> None:
        a = Allowlist()
        a.add_peer(_peer(1))
        a.add_multiaddr("/ip4/1.1.1.1")
        a.add_peer_multiaddr(_peer(2), "/ip4/2.2.2.2")
        a.clear()
        assert a.is_empty() is True

    def test_len_sums_all_categories(self) -> None:
        a = Allowlist()
        a.add_peer(_peer(1))
        a.add_peer(_peer(2))
        a.add_multiaddr("/ip4/1.1.1.1")
        a.add_peer_multiaddr(_peer(3), "/ip4/2.2.2.2")
        assert len(a) == 4

    def test_repr_contains_counts(self) -> None:
        a = Allowlist()
        a.add_peer(_peer(1))
        r = repr(a)
        assert "peers=1" in r
        assert "multiaddrs=0" in r
        assert "peer_multiaddrs=0" in r
