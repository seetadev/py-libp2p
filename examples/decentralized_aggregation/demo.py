"""
Decentralized Federated Learning Demo (Issue #22).

Simulates:
1. Round-robin leader rotation with sample-weighted averaging.
2. Pairwise gossip averaging across a mesh topology.
"""

from __future__ import (
    annotations,
)

import dataclasses
import logging
import random

import trio

from libp2p.federated.aggregation import (
    compute_peer_variance,
)
from libp2p.federated.gossip import (
    GossipAggregator,
)
from libp2p.federated.round_robin import (
    RoundRobinAggregator,
)

logger = logging.getLogger("demo")


@dataclasses.dataclass
class DemoPubsubMsg:
    data: bytes
    from_id: str
    topicIDs: list[str]


class DemoSub:
    def __init__(self, ch: trio.MemoryReceiveChannel[DemoPubsubMsg]) -> None:
        self.ch = ch

    async def get(self) -> DemoPubsubMsg:
        return await self.ch.receive()

    def unsubscribe(self) -> None:
        pass


class DemoPubsub:
    def __init__(self, peer_id: str, network: DemoPubsubNetwork) -> None:
        self.peer_id = peer_id
        self.network = network

    async def subscribe(self, topic: str) -> DemoSub:
        send_ch, recv_ch = trio.open_memory_channel[DemoPubsubMsg](100)
        self.network.add_sub(topic, send_ch)
        return DemoSub(recv_ch)

    async def publish(self, topic: str, data: bytes) -> None:
        msg = DemoPubsubMsg(data=data, from_id=self.peer_id, topicIDs=[topic])
        await self.network.broadcast(topic, msg)


class DemoPubsubNetwork:
    """In-memory pubsub bus connecting simulated peers."""

    def __init__(self) -> None:
        self.topics: dict[str, list[trio.MemorySendChannel[DemoPubsubMsg]]] = {}

    def add_sub(
        self,
        topic: str,
        ch: trio.MemorySendChannel[DemoPubsubMsg],
    ) -> None:
        self.topics.setdefault(topic, []).append(ch)

    async def broadcast(self, topic: str, msg: DemoPubsubMsg) -> None:
        for ch in list(self.topics.get(topic, [])):
            try:
                ch.send_nowait(msg)
            except trio.WouldBlock:
                await ch.send(msg)
            except (trio.ClosedResourceError, trio.BrokenResourceError):
                pass

    def create_nodes(self, count: int) -> list[DemoPubsub]:
        return [DemoPubsub(f"12D3KooWPeer{i + 1}", self) for i in range(count)]


async def run_round_robin(num_peers: int = 4, num_rounds: int = 4) -> None:
    print("\n--- Strategy 1: Round-Robin Aggregator Rotation ---")
    print(
        f"Config: {num_peers} peers, {num_rounds} training rounds, "
        "sample-weighted averaging\n"
    )

    network = DemoPubsubNetwork()
    pubsubs = network.create_nodes(num_peers)
    peer_ids = [p.peer_id for p in pubsubs]
    sample_counts = [50, 150, 100, 200]

    initial_weights = [
        [round(random.uniform(-5.0, 5.0), 2) for _ in range(3)]
        for _ in range(num_peers)
    ]

    for i in range(num_peers):
        print(
            f"  {peer_ids[i]} (samples={sample_counts[i]}): "
            f"initial weights = {initial_weights[i]}"
        )

    topic_prefix = f"federated/demo_rr_{random.randint(1000, 9999)}"
    aggregators = [
        RoundRobinAggregator(
            peer_id=peer_ids[i],
            pubsub=pubsubs[i],  # type: ignore[arg-type]
            participants=peer_ids,
            initial_weights=initial_weights[i],
            topic_prefix=topic_prefix,
            weighted=True,
            num_samples=sample_counts[i],
        )
        for i in range(num_peers)
    ]

    for agg in aggregators:
        await agg.setup_subscriptions()

    for r in range(num_rounds):
        leader_id = aggregators[0].get_leader(r)

        local_step_weights = []
        for i in range(num_peers):
            curr = aggregators[i].current_weights
            updated = [round(w + random.uniform(-0.3, 0.3), 3) for w in curr]
            local_step_weights.append(updated)

        results: list[list[float]] = [[] for _ in range(num_peers)]

        async def _run_peer(idx: int) -> None:
            results[idx] = await aggregators[idx].run_round(
                round_id=r,
                local_weights=local_step_weights[idx],
                timeout=2.0,
            )

        async with trio.open_nursery() as nursery:
            for i in range(num_peers):
                nursery.start_soon(_run_peer, i)

        global_model = [round(w, 3) for w in results[0]]
        var = compute_peer_variance([agg.current_weights for agg in aggregators])
        print(
            f"[Round {r + 1}/{num_rounds}] Leader={leader_id} -> "
            f"Global model: {global_model} (variance={var:.6f})"
        )

    print("Round-robin complete: all peers synchronized.\n")


async def run_gossip_averaging(num_peers: int = 4, num_steps: int = 5) -> None:
    print("--- Strategy 2: Decentralized Gossip Averaging ---")
    print(
        f"Config: {num_peers} peers, {num_steps} pairwise diffusion steps, "
        "mixing gamma=0.5\n"
    )

    network = DemoPubsubNetwork()
    pubsubs = network.create_nodes(num_peers)
    peer_ids = [p.peer_id for p in pubsubs]

    initial_weights = [
        [-10.0, 0.0, 10.0],
        [10.0, -10.0, 0.0],
        [0.0, 10.0, -10.0],
        [5.0, 5.0, 5.0],
    ]

    for i in range(num_peers):
        print(f"  {peer_ids[i]}: start weights = {initial_weights[i]}")

    init_var = compute_peer_variance(initial_weights)
    print(f"\nInitial model variance across peers: {init_var:.4f}")

    topic = f"federated/demo_gossip_{random.randint(1000, 9999)}"
    aggregators = [
        GossipAggregator(
            peer_id=peer_ids[i],
            pubsub=pubsubs[i],  # type: ignore[arg-type]
            initial_weights=initial_weights[i],
            topic=topic,
            mixing_rate=0.5,
        )
        for i in range(num_peers)
    ]

    async with trio.open_nursery() as nursery:
        for agg in aggregators:
            await agg.start(nursery, enable_periodic_broadcast=False)

        await trio.sleep(0.05)

        for step in range(num_steps):
            for agg in aggregators:
                await agg.broadcast_weights()

            await trio.sleep(0.05)

            current = [agg.current_weights for agg in aggregators]
            var = compute_peer_variance(current)
            drop = ((init_var - var) / init_var) * 100
            print(
                f"[Step {step + 1}/{num_steps}] Variance = {var:.4f} "
                f"(-{drop:.1f}% from start)"
            )

        for agg in aggregators:
            agg.stop()
        nursery.cancel_scope.cancel()

    print("Gossip diffusion complete: model weights converged across mesh.\n")


async def main() -> None:
    await run_round_robin(num_peers=4, num_rounds=4)
    await run_gossip_averaging(num_peers=4, num_steps=5)


def cli() -> None:
    trio.run(main)


if __name__ == "__main__":
    cli()
