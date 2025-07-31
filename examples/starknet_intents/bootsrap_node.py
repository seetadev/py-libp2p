import logging
import socket

from multiaddr import Multiaddr
from pubsub_intents import IntentPubSub
import trio_asyncio

from libp2p import new_host

TOPIC = "/starknet/intent/1.0.0"
LISTEN_ADDR = "/ip4/0.0.0.0/tcp/9000"  # Use 0.0.0.0 to bind on all interfaces

logger = logging.getLogger("bootstrap")
logging.basicConfig(level=logging.INFO)


async def run_bootstrap():
    """
    Launch a libp2p bootstrap node on port 9000.
    Prints peer ID and full multiaddress so other peers can connect.
    Receives and logs intents from GossipSub topic.
    """
    host = new_host()

    # Run the host listening on a chosen address
    async with host.run(listen_addrs=[Multiaddr(LISTEN_ADDR)]):
        logger.info("[BOOTSTRAP] ID: %s", host.get_id())
        for addr in host.get_addrs():
            addr_str = str(addr)
            if "0.0.0.0" in addr_str:
                # Replace 0.0.0.0 with local IP so it's dialable
                local_ip = socket.gethostbyname(socket.gethostname())
                addr_str = addr_str.replace("0.0.0.0", local_ip)
            full = f"{addr_str}/p2p/{host.get_id()}"
            logger.info("[DIAL USING] %s", full)

        pubsub = IntentPubSub(host, host.get_peerstore())

        async def handler(data: str):
            logger.info("[RECEIVED INTENT] %s", data)

        await pubsub.subscribe_and_handle(TOPIC, handler)


if __name__ == "__main__":
    trio_asyncio.run(run_bootstrap)
