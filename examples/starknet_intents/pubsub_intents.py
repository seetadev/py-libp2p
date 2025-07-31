import json

from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub

TOPIC = "/starknet/intent/1.0.0"


class IntentPubSub:
    def __init__(self, host, peerstore):
        degree = 6
        degree_low = 4
        degree_high = 12

        router = GossipSub(
            protocols=[TOPIC],
            degree=degree,
            degree_low=degree_low,
            degree_high=degree_high,
        )
        self.pubsub = Pubsub(host, router)

    async def subscribe_and_handle(self, topic, handler):
        sub = await self.pubsub.subscribe(topic)
        print(f"[SUBSCRIBED] to {topic}")

        # 🟢 Use a proper Trio loop
        async for msg in sub:
            try:
                decoded = msg.data.decode("utf-8")
                payload = json.loads(decoded)
                await handler(payload)
            except Exception as e:
                print(f"[ERROR] Failed to handle message: {e}")

    async def publish(self, topic, message: str):
        await self.pubsub.publish(topic, message.encode("utf-8"))
