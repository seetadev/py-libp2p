"""
Tests for the rcmgr memory_pool module.
"""

from __future__ import annotations

from libp2p.rcmgr.memory_pool import MemoryPool


class TestMemoryPool:
    def test_initial_pool_populated(self) -> None:
        pool = MemoryPool(block_size=64, initial_blocks=10)
        assert len(pool) == 10
        assert pool.get_stats()["total_created"] == 10
        assert pool.get_stats()["total_allocated"] == 0

    def test_acquire_returns_block_of_correct_size(self) -> None:
        pool = MemoryPool(block_size=128, initial_blocks=2)
        block = pool.acquire()
        assert block is not None
        assert len(block) == 128
        assert len(pool) == 1  # pool size decreased

    def test_acquire_beyond_preallocated_creates_new_when_under_max(self) -> None:
        pool = MemoryPool(
            block_size=32, initial_blocks=1, max_blocks=3
        )
        b1 = pool.acquire()
        b2 = pool.acquire()
        b3 = pool.acquire()
        assert b1 is not None and b2 is not None and b3 is not None
        stats = pool.get_stats()
        assert stats["total_created"] == 3
        assert stats["total_allocated"] == 3

    def test_acquire_returns_none_when_max_exhausted(self) -> None:
        pool = MemoryPool(block_size=32, initial_blocks=1, max_blocks=1)
        assert pool.acquire() is not None
        assert pool.acquire() is None

    def test_acquire_unlimited_when_max_blocks_is_none(self) -> None:
        pool = MemoryPool(block_size=16, initial_blocks=0, max_blocks=None)
        for _ in range(50):
            assert pool.acquire() is not None

    def test_release_returns_block_to_pool(self) -> None:
        pool = MemoryPool(block_size=32, initial_blocks=1, max_blocks=1)
        block = pool.acquire()
        assert len(pool) == 0
        pool.release(block)
        assert len(pool) == 1

    def test_release_zeros_block_contents(self) -> None:
        pool = MemoryPool(block_size=8, initial_blocks=1)
        block = pool.acquire()
        for i in range(len(block)):
            block[i] = 0xAB
        pool.release(block)
        # Pool zeros the block on release
        assert bytes(block) == b"\x00" * 8

    def test_release_ignores_wrong_sized_block(self) -> None:
        pool = MemoryPool(block_size=8, initial_blocks=1)
        wrong = bytearray(16)
        pool.release(wrong)  # must not raise, must not add
        assert len(pool) == 1

    def test_release_does_not_exceed_max_blocks(self) -> None:
        # pool capacity is implicit: (max_blocks or total_created) at release time
        pool = MemoryPool(block_size=8, initial_blocks=1, max_blocks=1)
        block = pool.acquire()
        pool.release(block)
        # Try to over-fill by acquiring + releasing a new block
        block2 = pool.acquire()
        pool.release(block2)
        assert len(pool) == 1  # capped at max_blocks

    def test_get_stats_utilization(self) -> None:
        pool = MemoryPool(block_size=8, initial_blocks=4)
        pool.acquire()
        pool.acquire()
        stats = pool.get_stats()
        assert stats["utilization"] == 0.5  # 2 allocated / 4 created
        assert stats["pool_size"] == 2
        assert stats["block_size"] == 8
        assert stats["max_blocks"] is None

    def test_clear_resets_state(self) -> None:
        pool = MemoryPool(block_size=8, initial_blocks=2)
        block = pool.acquire()
        pool.release(block)
        pool.clear()
        assert len(pool) == 0
        stats = pool.get_stats()
        assert stats["total_created"] == 0
        assert stats["total_allocated"] == 0

    def test_bool_returns_true_only_when_blocks_available(self) -> None:
        pool = MemoryPool(block_size=8, initial_blocks=1)
        assert bool(pool) is True
        pool.acquire()
        assert bool(pool) is False

    def test_acquire_after_clear_with_max_blocks(self) -> None:
        pool = MemoryPool(block_size=8, initial_blocks=2, max_blocks=4)
        pool.clear()
        # After clear, total_created is 0 so acquire can create up to max_blocks
        blocks = [pool.acquire() for _ in range(4)]
        assert all(b is not None for b in blocks)
        assert pool.acquire() is None
