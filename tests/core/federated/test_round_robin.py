from __future__ import (
    annotations,
)

import pytest
import trio

from libp2p.federated.round_robin import (
    RoundRobinAggregator,
)
from tests.core.federated.mock_pubsub import (
    SimulatedPubsubNetwork,
)


def test_leader_determination() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(3)
    peer_ids = [n.peer_id for n in nodes]
    agg = RoundRobinAggregator(
        peer_id=peer_ids[0],
        pubsub=nodes[0],  # type: ignore[arg-type]
        participants=peer_ids,
        initial_weights=[0.0, 0.0],
    )
    assert agg.get_leader(0) == sorted(peer_ids)[0]
    assert agg.get_leader(1) == sorted(peer_ids)[1]
    assert agg.get_leader(2) == sorted(peer_ids)[2]
    assert agg.get_leader(3) == sorted(peer_ids)[0]


async def test_round_robin_single_round() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(3)
    peer_ids = [n.peer_id for n in nodes]

    aggregators = [
        RoundRobinAggregator(
            peer_id=peer_ids[i],
            pubsub=nodes[i],  # type: ignore[arg-type]
            participants=peer_ids,
            initial_weights=[float(i), float(i * 2)],
            weighted=False,
        )
        for i in range(3)
    ]

    for agg in aggregators:
        await agg.setup_subscriptions()

    results: list[list[float]] = [[] for _ in range(3)]

    async def run_round_peer(idx: int) -> None:
        results[idx] = await aggregators[idx].run_round(
            round_id=0,
            local_weights=[float(idx * 10), float(idx * 10)],
            timeout=1.0,
        )

    async with trio.open_nursery() as nursery:
        for i in range(3):
            nursery.start_soon(run_round_peer, i)

    expected = [10.0, 10.0]
    for r in results:
        assert r == pytest.approx(expected, abs=1e-5)


async def test_round_robin_leader_rotation_3_rounds() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(3)
    peer_ids = [n.peer_id for n in nodes]

    aggregators = [
        RoundRobinAggregator(
            peer_id=peer_ids[i],
            pubsub=nodes[i],  # type: ignore[arg-type]
            participants=peer_ids,
            initial_weights=[0.0, 0.0],
            weighted=False,
        )
        for i in range(3)
    ]

    for agg in aggregators:
        await agg.setup_subscriptions()

    for r in range(3):
        results: list[list[float]] = [[] for _ in range(3)]

        async def run_round_peer(idx: int, round_num: int) -> None:
            w0 = aggregators[idx].current_weights[0] + 1.0
            w1 = aggregators[idx].current_weights[1] + 2.0
            results[idx] = await aggregators[idx].run_round(
                round_id=round_num,
                local_weights=[w0, w1],
                timeout=1.0,
            )

        async with trio.open_nursery() as nursery:
            for i in range(3):
                nursery.start_soon(run_round_peer, i, r)

        assert results[0] == results[1] == results[2]


async def test_round_robin_weighted() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(2)
    peer_ids = [n.peer_id for n in nodes]

    aggregators = [
        RoundRobinAggregator(
            peer_id=peer_ids[0],
            pubsub=nodes[0],  # type: ignore[arg-type]
            participants=peer_ids,
            initial_weights=[0.0],
            weighted=True,
            num_samples=100,
        ),
        RoundRobinAggregator(
            peer_id=peer_ids[1],
            pubsub=nodes[1],  # type: ignore[arg-type]
            participants=peer_ids,
            initial_weights=[0.0],
            weighted=True,
            num_samples=300,
        ),
    ]

    for agg in aggregators:
        await agg.setup_subscriptions()

    results: list[list[float]] = [[] for _ in range(2)]

    async def run_round_peer(idx: int, weight: float) -> None:
        results[idx] = await aggregators[idx].run_round(
            round_id=0,
            local_weights=[weight],
            timeout=1.0,
        )

    async with trio.open_nursery() as nursery:
        nursery.start_soon(run_round_peer, 0, 10.0)
        nursery.start_soon(run_round_peer, 1, 20.0)

    # Expected: (10*100 + 20*300) / 400 = 7000 / 400 = 17.5
    assert results[0] == pytest.approx([17.5], abs=1e-5)
    assert results[1] == pytest.approx([17.5], abs=1e-5)
