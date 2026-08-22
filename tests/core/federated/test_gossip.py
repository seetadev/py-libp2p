from __future__ import (
    annotations,
)

import pytest
import trio

from libp2p.federated.aggregation import (
    compute_peer_variance,
)
from libp2p.federated.gossip import (
    GossipAggregator,
)
from libp2p.federated.payload import (
    ModelPayload,
)
from tests.core.federated.mock_pubsub import (
    SimulatedPubsubNetwork,
)


async def test_gossip_process_payload_logic() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(2)

    agg = GossipAggregator(
        peer_id=nodes[0].peer_id,
        pubsub=nodes[0],  # type: ignore[arg-type]
        initial_weights=[0.0, 10.0],
        mixing_rate=0.5,
    )

    # Self-message ignored
    self_payload = ModelPayload(
        sender_id=nodes[0].peer_id,
        round_id=0,
        weights=[5.0, 5.0],
    )
    assert not await agg.process_incoming_payload(self_payload)
    assert agg.current_weights == [0.0, 10.0]

    # Remote message processed
    remote_payload = ModelPayload(
        sender_id=nodes[1].peer_id,
        round_id=0,
        weights=[10.0, 20.0],
    )
    assert await agg.process_incoming_payload(remote_payload)
    assert agg.current_weights == [5.0, 15.0]


async def test_gossip_two_peers_exchange() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(2)

    agg1 = GossipAggregator(
        peer_id=nodes[0].peer_id,
        pubsub=nodes[0],  # type: ignore[arg-type]
        initial_weights=[0.0],
        mixing_rate=0.5,
    )
    agg2 = GossipAggregator(
        peer_id=nodes[1].peer_id,
        pubsub=nodes[1],  # type: ignore[arg-type]
        initial_weights=[10.0],
        mixing_rate=0.5,
    )

    async with trio.open_nursery() as nursery:
        await agg1.start(nursery, enable_periodic_broadcast=False)
        await agg2.start(nursery, enable_periodic_broadcast=False)

        await trio.sleep(0.05)

        # Peer 1 broadcasts [0.0] -> Peer 2 updates to 5.0
        await agg1.broadcast_weights()
        await trio.sleep(0.05)
        assert agg2.current_weights == pytest.approx([5.0], abs=1e-5)

        # Peer 2 broadcasts [5.0] -> Peer 1 updates to 2.5
        await agg2.broadcast_weights()
        await trio.sleep(0.05)
        assert agg1.current_weights == pytest.approx([2.5], abs=1e-5)

        agg1.stop()
        agg2.stop()
        nursery.cancel_scope.cancel()


async def test_gossip_multi_peer_variance_reduction() -> None:
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(4)
    initial_weights = [
        [-10.0, 0.0],
        [10.0, -10.0],
        [0.0, 10.0],
        [5.0, 5.0],
    ]

    aggregators = [
        GossipAggregator(
            peer_id=nodes[i].peer_id,
            pubsub=nodes[i],  # type: ignore[arg-type]
            initial_weights=initial_weights[i],
            mixing_rate=0.5,
        )
        for i in range(4)
    ]

    initial_variance = compute_peer_variance(initial_weights)

    async with trio.open_nursery() as nursery:
        for agg in aggregators:
            await agg.start(nursery, enable_periodic_broadcast=False)

        await trio.sleep(0.05)

        for _ in range(5):
            for agg in aggregators:
                await agg.broadcast_weights()
            await trio.sleep(0.02)

        final_variance = compute_peer_variance(
            [agg.current_weights for agg in aggregators]
        )
        assert final_variance < initial_variance * 0.1

        for agg in aggregators:
            agg.stop()
        nursery.cancel_scope.cancel()


async def test_gossip_concurrent_loops_default_usage() -> None:
    """Runs both loops together (enable_periodic_broadcast=True, the default)."""
    network = SimulatedPubsubNetwork()
    nodes = network.create_peers(2)

    agg1 = GossipAggregator(
        peer_id=nodes[0].peer_id,
        pubsub=nodes[0],  # type: ignore[arg-type]
        initial_weights=[0.0],
        mixing_rate=0.5,
        gossip_interval=0.05,
    )
    agg2 = GossipAggregator(
        peer_id=nodes[1].peer_id,
        pubsub=nodes[1],  # type: ignore[arg-type]
        initial_weights=[10.0],
        mixing_rate=0.5,
        gossip_interval=0.05,
    )

    with trio.move_on_after(3) as cancel_scope:
        async with trio.open_nursery() as nursery:
            await agg1.start(nursery)
            await agg2.start(nursery)

            await trio.sleep(0.5)

            agg1.stop()
            agg2.stop()
            nursery.cancel_scope.cancel()

    assert not cancel_scope.cancelled_caught
    assert agg1.current_weights == pytest.approx([5.0], abs=1.0)
    assert agg2.current_weights == pytest.approx([5.0], abs=1.0)