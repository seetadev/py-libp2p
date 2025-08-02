from collections.abc import Awaitable, Callable
import json
from typing import Any, cast

from libp2p.custom_types import TProtocol
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub

TOPIC = "/starknet/intent/1.0.0"


class IntentPubSub:
    def __init__(self, host: Any, peerstore: Any) -> None:
        degree = 6
        degree_low = 4
        degree_high = 12

        router = GossipSub(
            protocols=[cast(TProtocol, TOPIC)],
            degree=degree,
            degree_low=degree_low,
            degree_high=degree_high,
        )
        self.pubsub = Pubsub(host, router)

    async def subscribe_and_handle(
        self, topic: str, handler: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        sub = await self.pubsub.subscribe(topic)
        print(f"[SUBSCRIBED] to {topic}")

        async for msg in sub:
            try:
                decoded = msg.data.decode("utf-8")
                payload = json.loads(decoded)
                await handler(payload)
            except Exception as e:
                print(f"[ERROR] Failed to handle message: {e}")

    async def publish(self, topic: str, message: str) -> None:
        await self.pubsub.publish(topic, message.encode("utf-8"))
