from __future__ import (
    annotations,
)

from collections.abc import (
    Callable,
    Sequence,
)
import logging
from typing import (
    Any,
)

import trio

from libp2p.federated.aggregation import (
    pairwise_mix,
)
from libp2p.federated.payload import (
    ModelPayload,
)
from libp2p.pubsub.pubsub import (
    Pubsub,
)

logger = logging.getLogger("libp2p.federated.gossip")


class GossipAggregator:
    """Decentralized continuous gossip-based model aggregator."""

    def __init__(
        self,
        peer_id: str,
        pubsub: Pubsub,
        initial_weights: Sequence[float],
        topic: str = "federated/gossip/v1",
        mixing_rate: float = 0.5,
        num_samples: int = 1,
        gossip_interval: float = 1.0,
        on_update_callback: Callable[[list[float], str], None] | None = None,
    ) -> None:
        self.peer_id = str(peer_id)
        self.pubsub = pubsub
        self.topic = topic
        self.weights: list[float] = [float(w) for w in initial_weights]
        self.mixing_rate = float(mixing_rate)
        self.num_samples = int(num_samples)
        self.gossip_interval = float(gossip_interval)
        self.on_update_callback = on_update_callback

        self.update_count: int = 0
        self.received_messages: int = 0
        self._termination_event: trio.Event = trio.Event()
        self._receive_scope: trio.CancelScope | None = None
        self._gossip_scope: trio.CancelScope | None = None
        self._subscription: Any = None

    @property
    def current_weights(self) -> list[float]:
        return list(self.weights)

    async def broadcast_weights(self) -> None:
        payload = ModelPayload(
            sender_id=self.peer_id,
            round_id=self.update_count,
            weights=self.weights,
            num_samples=self.num_samples,
        )
        await self.pubsub.publish(self.topic, payload.to_bytes())

    async def process_incoming_payload(self, payload: ModelPayload) -> bool:
        if payload.sender_id == self.peer_id:
            return False

        self.weights = pairwise_mix(
            local_weights=self.weights,
            remote_weights=payload.weights,
            gamma=self.mixing_rate,
        )
        self.received_messages += 1
        self.update_count += 1

        if self.on_update_callback:
            try:
                self.on_update_callback(self.weights, payload.sender_id)
            except Exception as exc:
                logger.debug(f"on_update_callback error: {exc}")

        return True

    async def _receive_loop(self, subscription: Any) -> None:
        with trio.CancelScope() as scope:
            self._receive_scope = scope
            while not self._termination_event.is_set():
                try:
                    msg = await subscription.get()
                    payload = ModelPayload.from_bytes(msg.data)
                    await self.process_incoming_payload(payload)
                except Exception as exc:
                    if self._termination_event.is_set():
                        break
                    logger.debug(f"Receive loop error: {exc}")
                    await trio.sleep(0.05)

    async def _periodic_gossip_loop(self) -> None:
        with trio.CancelScope() as scope:
            self._gossip_scope = scope
            while not self._termination_event.is_set():
                try:
                    await self.broadcast_weights()
                    await trio.sleep(self.gossip_interval)
                except Exception as exc:
                    if self._termination_event.is_set():
                        break
                    logger.debug(f"Periodic loop error: {exc}")
                    await trio.sleep(0.5)

    async def start(
        self,
        nursery: trio.Nursery,
        enable_periodic_broadcast: bool = True,
    ) -> None:
        self._subscription = await self.pubsub.subscribe(self.topic)
        nursery.start_soon(self._receive_loop, self._subscription)
        if enable_periodic_broadcast:
            nursery.start_soon(self._periodic_gossip_loop)

    def stop(self) -> None:
        self._termination_event.set()
        if self._receive_scope is not None:
            self._receive_scope.cancel()
        if self._gossip_scope is not None:
            self._gossip_scope.cancel()
        if self._subscription and hasattr(self._subscription, "unsubscribe"):
            try:
                self._subscription.unsubscribe()
            except Exception:
                pass
