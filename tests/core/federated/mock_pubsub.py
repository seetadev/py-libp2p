"""
In-memory PubSub network simulator for deterministic, fast testing
without external dependencies or port binding.
"""

from __future__ import (
    annotations,
)

import dataclasses

import trio


@dataclasses.dataclass
class SimulatedPubsubMessage:
    data: bytes
    from_id: str
    topicIDs: list[str]


class SimulatedSubscription:
    def __init__(
        self,
        recv_channel: trio.MemoryReceiveChannel[SimulatedPubsubMessage],
    ) -> None:
        self._recv_channel = recv_channel

    async def get(self) -> SimulatedPubsubMessage:
        return await self._recv_channel.receive()

    def unsubscribe(self) -> None:
        pass


class SimulatedHostID:
    def __init__(self, peer_id: str) -> None:
        self._peer_id = peer_id

    def to_base58(self) -> str:
        return self._peer_id

    def to_string(self) -> str:
        return self._peer_id

    def __str__(self) -> str:
        return self._peer_id


class SimulatedHost:
    def __init__(self, peer_id: str) -> None:
        self._peer_id = peer_id

    def get_id(self) -> SimulatedHostID:
        return SimulatedHostID(self._peer_id)


class SimulatedPubsub:
    def __init__(self, peer_id: str, network: SimulatedPubsubNetwork) -> None:
        self.peer_id = peer_id
        self.network = network
        self.host = SimulatedHost(peer_id)

    async def subscribe(self, topic: str) -> SimulatedSubscription:
        send_ch, recv_ch = trio.open_memory_channel[SimulatedPubsubMessage](100)
        self.network.register_subscriber(topic, send_ch)
        return SimulatedSubscription(recv_ch)

    async def publish(self, topic: str, data: bytes) -> None:
        msg = SimulatedPubsubMessage(
            data=data,
            from_id=self.peer_id,
            topicIDs=[topic],
        )
        await self.network.broadcast(topic, msg)


class SimulatedPubsubNetwork:
    """Manages virtual pubsub routing between peers in tests."""

    def __init__(self) -> None:
        self._topics: dict[
            str, list[trio.MemorySendChannel[SimulatedPubsubMessage]]
        ] = {}

    def register_subscriber(
        self,
        topic: str,
        send_channel: trio.MemorySendChannel[SimulatedPubsubMessage],
    ) -> None:
        if topic not in self._topics:
            self._topics[topic] = []
        self._topics[topic].append(send_channel)

    async def broadcast(self, topic: str, msg: SimulatedPubsubMessage) -> None:
        channels = list(self._topics.get(topic, []))
        for ch in channels:
            try:
                ch.send_nowait(msg)
            except trio.WouldBlock:
                await ch.send(msg)
            except (trio.ClosedResourceError, trio.BrokenResourceError):
                pass

    def create_peers(self, count: int) -> list[SimulatedPubsub]:
        return [
            SimulatedPubsub(peer_id=f"QmSimulatedPeer{i:03d}", network=self)
            for i in range(count)
        ]
