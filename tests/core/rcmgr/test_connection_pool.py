"""
Tests for the rcmgr connection_pool module.
"""

from __future__ import annotations

from libp2p.rcmgr.connection_pool import ConnectionPool


class _Conn:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Conn({self.n})"


class TestConnectionPoolFactory:
    def test_pre_allocate_with_factory(self) -> None:
        counter = {"n": 0}

        def factory() -> _Conn:
            counter["n"] += 1
            return _Conn(counter["n"])

        pool = ConnectionPool[_Conn](
            max_size=10, pre_allocate=True, connection_factory=factory
        )
        # 10/4 = 2, min(100, 2) = 2
        assert counter["n"] == 2
        assert pool.get_stats()["pool_size"] == 2

    def test_pre_allocate_without_factory(self) -> None:
        pool = ConnectionPool(max_size=10, pre_allocate=True)
        assert pool.get_stats()["pool_size"] == 0

    def test_pre_allocate_disabled(self) -> None:
        counter = {"n": 0}

        def factory() -> _Conn:
            counter["n"] += 1
            return _Conn(counter["n"])

        pool = ConnectionPool[_Conn](
            max_size=10, pre_allocate=False, connection_factory=factory
        )
        assert counter["n"] == 0

    def test_factory_exception_during_pre_allocation_stops(self) -> None:
        # max_size=20 -> pre_alloc_count = min(100, 20//4) = 5
        counter = {"n": 0}

        def factory() -> _Conn:
            counter["n"] += 1
            if counter["n"] > 3:
                raise RuntimeError("boom")
            return _Conn(counter["n"])

        pool = ConnectionPool[_Conn](
            max_size=20, pre_allocate=True, connection_factory=factory
        )
        # Should stop on first failure (4th call)
        assert counter["n"] == 4
        assert pool.get_stats()["pool_size"] == 3


class TestConnectionPoolAcquire:
    def test_acquire_from_pre_allocated(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=4,
            pre_allocate=True,
            connection_factory=lambda: _Conn(1),
        )
        c = pool.acquire()
        assert c is not None
        assert c in pool._active
        assert len(pool) == 1

    def test_acquire_creates_new_when_under_max(self) -> None:
        counter = {"n": 0}

        def factory() -> _Conn:
            counter["n"] += 1
            return _Conn(counter["n"])

        pool = ConnectionPool[_Conn](
            max_size=4, pre_allocate=False, connection_factory=factory
        )
        c = pool.acquire()
        assert c is not None
        assert counter["n"] == 1

    def test_acquire_returns_none_when_full(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=2,
            pre_allocate=False,
            connection_factory=lambda: _Conn(1),
        )
        assert pool.acquire() is not None
        assert pool.acquire() is not None
        assert pool.acquire() is None

    def test_acquire_returns_none_when_factory_raises(self) -> None:
        def factory() -> _Conn:
            raise RuntimeError("nope")

        pool = ConnectionPool[_Conn](
            max_size=2, pre_allocate=False, connection_factory=factory
        )
        assert pool.acquire() is None

    def test_acquire_no_factory_no_prealloc(self) -> None:
        pool = ConnectionPool(max_size=2, pre_allocate=False)
        assert pool.acquire() is None


class TestConnectionPoolRelease:
    def test_release_removes_from_active(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=2, pre_allocate=True, connection_factory=lambda: _Conn(1)
        )
        c = pool.acquire()
        assert len(pool) == 1
        pool.release(c)
        assert len(pool) == 0

    def test_release_returns_to_pool_when_under_capacity(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=10,
            pre_allocate=False,
            connection_factory=lambda: _Conn(1),
        )
        c1 = pool.acquire()
        c2 = pool.acquire()
        pool.release(c1)
        # max_size // 2 = 5, pool size before release was 0 -> add
        stats = pool.get_stats()
        assert stats["pool_size"] == 1
        pool.release(c2)
        assert pool.get_stats()["pool_size"] == 2

    def test_release_unknown_connection_does_not_raise(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=2, pre_allocate=False, connection_factory=lambda: _Conn(1)
        )
        pool.release(_Conn(999))  # not in active
        assert pool.get_stats()["active_connections"] == 0


class TestConnectionPoolStats:
    def test_utilization(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=4, pre_allocate=False, connection_factory=lambda: _Conn(1)
        )
        assert pool.get_stats()["utilization"] == 0.0
        pool.acquire()
        pool.acquire()
        assert pool.get_stats()["utilization"] == 0.5

    def test_utilization_zero_max_size(self) -> None:
        pool = ConnectionPool(max_size=0, pre_allocate=False)
        assert pool.get_stats()["utilization"] == 0.0

    def test_clear(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=4, pre_allocate=True, connection_factory=lambda: _Conn(1)
        )
        pool.acquire()
        pool.clear()
        assert pool.get_stats()["pool_size"] == 0
        assert pool.get_stats()["active_connections"] == 0
        assert pool.get_stats()["total_created"] == 0

    def test_bool(self) -> None:
        pool = ConnectionPool[_Conn](
            max_size=2, pre_allocate=False, connection_factory=lambda: _Conn(1)
        )
        assert bool(pool) is False
        c = pool.acquire()
        assert bool(pool) is True
        pool.release(c)
        assert bool(pool) is False
