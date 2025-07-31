import json
import logging

from discovery import bootstrap_to_peer
from intents import create_intent
from multiaddr import Multiaddr
from pubsub_intents import IntentPubSub
import trio
import trio_asyncio

from libp2p import new_host

logger = logging.getLogger("peer")
logging.basicConfig(level=logging.INFO)

TOPIC = "/starknet/intent/1.0.0"


async def run_peer(bootstrap_addr: str):
    """
    Launch a libp2p peer node, connect to bootstrap,
    subscribe to the intent topic, and publish a test intent.
    """
    host = new_host()

    # Ensure peer listens on a port as well (same port used by bootstrap for NAT)
    async with host.run(listen_addrs=[Multiaddr("/ip4/0.0.0.0/tcp/0")]):
        logger.info("[PEER] ID: %s", host.get_id())

        await bootstrap_to_peer(host, bootstrap_addr)

        pub = IntentPubSub(host, host.get_peerstore())

        async def handler(intent: str):
            logger.info("[PEER RECEIVED] %s", intent)

        async with trio.open_nursery() as nursery:
            nursery.start_soon(pub.subscribe_and_handle, TOPIC, handler)
            await trio.sleep(1)

            intent = create_intent("0xSender", "0xContract", [1, 2], 123456)
            await pub.publish(TOPIC, json.dumps(intent))
            logger.info("[PEER] Intent sent")

            await trio.sleep_forever()


if __name__ == "__main__":
    import sys

    trio_asyncio.run(lambda: run_peer(sys.argv[1]))
