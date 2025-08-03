import logging
import socket
from typing import Any

from multiaddr import Multiaddr
import trio_asyncio

from libp2p import new_host
from libp2p.starknet_intents.pubsub_intents import IntentPubSub

TOPIC = "/starknet/intent/1.0.0"
LISTEN_ADDR = "/ip4/0.0.0.0/tcp/9000"
logger = logging.getLogger("bootstrap")
logging.basicConfig(level=logging.INFO)


async def run_bootstrap() -> None:
    """
    Launch a libp2p bootstrap node on port 9000.
    Prints peer ID and full multiaddress so other peers can connect.
    Receives and logs intents from GossipSub topic.
    """
    host = new_host()

    async with host.run(listen_addrs=[Multiaddr(LISTEN_ADDR)]):
        logger.info("[BOOTSTRAP] ID: %s", host.get_id())
        for addr in host.get_addrs():
            addr_str = str(addr)
            if "0.0.0.0" in addr_str:
                local_ip = socket.gethostbyname(socket.gethostname())
                addr_str = addr_str.replace("0.0.0.0", local_ip)
            full = f"{addr_str}/p2p/{host.get_id()}"
            logger.info("[DIAL USING] %s", full)

        pubsub = IntentPubSub(host, host.get_peerstore())

        async def handler(data: dict[str, Any]) -> None:
            logger.info("[RECEIVED INTENT] %s", data)

        await pubsub.subscribe_and_handle(TOPIC, handler)


if __name__ == "__main__":
    trio_asyncio.run(run_bootstrap)
