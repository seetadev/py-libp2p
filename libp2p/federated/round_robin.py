from __future__ import (
    annotations,
)

from collections.abc import (
    Sequence,
)
import logging
from typing import (
    Any,
)

import trio

from libp2p.federated.aggregation import (
    uniform_average,
    weighted_average,
)
from libp2p.federated.payload import (
    ModelPayload,
)
from libp2p.pubsub.pubsub import (
    Pubsub,
)

logger = logging.getLogger("libp2p.federated.round_robin")


class RoundRobinAggregator:
    """
    Round-robin coordinator for decentralized federated learning.

    Precondition:
        All participating peers must be initialized with the exact same
        list/set of `participants`. The aggregator sorts peer IDs
        lexicographically so that every node independently and
        deterministically resolves the identical leader for round `r`
        without central consensus: `leader(r) = sorted(participants)[r % N]`.
    """

    def __init__(
        self,
        peer_id: str,
        pubsub: Pubsub,
        participants: Sequence[str],
        initial_weights: Sequence[float],
        topic_prefix: str = "federated/round_robin",
        weighted: bool = True,
        num_samples: int = 1,
        min_quorum_ratio: float = 0.5,
    ) -> None:
        if not participants:
            raise ValueError("Participants list cannot be empty")

        self.peer_id = str(peer_id)
        self.pubsub = pubsub
        self.participants = sorted(set(str(p) for p in participants))
        self.weights: list[float] = [float(w) for w in initial_weights]
        self.topic_prefix = topic_prefix.rstrip("/")
        self.updates_topic = f"{self.topic_prefix}/updates"
        self.global_topic = f"{self.topic_prefix}/global"
        self.weighted = weighted
        self.num_samples = int(num_samples)
        self.min_quorum_ratio = max(0.1, min(1.0, min_quorum_ratio))

        self.current_round: int = 0
        self._updates_sub: Any = None
        self._global_sub: Any = None
        self._is_ready: bool = False

    @property
    def current_weights(self) -> list[float]:
        return list(self.weights)

    def get_leader(self, round_id: int) -> str:
        idx = round_id % len(self.participants)
        return self.participants[idx]

    def is_leader(self, round_id: int) -> bool:
        return self.get_leader(round_id) == self.peer_id

    async def setup_subscriptions(self) -> None:
        if not self._is_ready:
            self._updates_sub = await self.pubsub.subscribe(self.updates_topic)
            self._global_sub = await self.pubsub.subscribe(self.global_topic)
            self._is_ready = True

    async def run_round(
        self,
        round_id: int,
        local_weights: Sequence[float] | None = None,
        timeout: float = 5.0,
    ) -> list[float]:
        await self.setup_subscriptions()
        self.current_round = round_id

        if local_weights is not None:
            self.weights = [float(w) for w in local_weights]

        leader = self.get_leader(round_id)
        if self.peer_id == leader:
            return await self._run_leader_round(round_id, timeout)
        else:
            return await self._run_follower_round(round_id, leader, timeout)

    async def _run_leader_round(
        self,
        round_id: int,
        timeout: float,
    ) -> list[float]:
        collected_updates: dict[str, ModelPayload] = {
            self.peer_id: ModelPayload(
                sender_id=self.peer_id,
                round_id=round_id,
                weights=self.weights,
                num_samples=self.num_samples,
            )
        }

        min_required = max(1, int(len(self.participants) * self.min_quorum_ratio))
        deadline = trio.current_time() + timeout

        # Collect updates until all participants have responded, or until the timeout
        # deadline expires to maximize participant contributions.
        while len(collected_updates) < len(self.participants):
            remaining = deadline - trio.current_time()
            if remaining <= 0:
                break

            with trio.move_on_after(remaining):
                msg = await self._updates_sub.get()
                try:
                    payload = ModelPayload.from_bytes(msg.data)
                    is_valid_peer = payload.sender_id in self.participants
                    if payload.round_id == round_id and is_valid_peer:
                        collected_updates[payload.sender_id] = payload
                except Exception as exc:
                    logger.debug(f"Failed to decode update payload: {exc}")

        # If collected updates meet the quorum threshold, aggregate them.
        # Otherwise fallback to local weights.
        if len(collected_updates) < min_required:
            aggregated = self.weights
        else:
            weight_list = [p.weights for p in collected_updates.values()]
            sample_list = [p.num_samples for p in collected_updates.values()]
            if self.weighted:
                aggregated = weighted_average(weight_list, sample_list)
            else:
                aggregated = uniform_average(weight_list)

        self.weights = aggregated

        global_payload = ModelPayload(
            sender_id=self.peer_id,
            round_id=round_id,
            weights=self.weights,
            num_samples=sum(p.num_samples for p in collected_updates.values()),
            metadata={
                "aggregator": self.peer_id,
                "num_contributors": len(collected_updates),
            },
        )
        await self.pubsub.publish(self.global_topic, global_payload.to_bytes())
        return self.weights

    async def _run_follower_round(
        self,
        round_id: int,
        expected_leader: str,
        timeout: float,
    ) -> list[float]:
        local_payload = ModelPayload(
            sender_id=self.peer_id,
            round_id=round_id,
            weights=self.weights,
            num_samples=self.num_samples,
        )
        await self.pubsub.publish(self.updates_topic, local_payload.to_bytes())

        with trio.move_on_after(timeout):
            while True:
                msg = await self._global_sub.get()
                try:
                    payload = ModelPayload.from_bytes(msg.data)
                    matches_round = payload.round_id == round_id
                    matches_leader = payload.sender_id == expected_leader
                    if matches_round and matches_leader:
                        self.weights = payload.weights
                        return self.weights
                except Exception as exc:
                    logger.debug(f"Failed to decode global payload: {exc}")

        return self.weights
