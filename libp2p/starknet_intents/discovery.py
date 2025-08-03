import logging
from typing import Any

from multiaddr import Multiaddr

from libp2p.peer.peerinfo import info_from_p2p_addr


async def bootstrap_to_peer(host: Any, bootstrap_addr_str: str) -> None:
    logger = logging.getLogger("peer")
    logger.info("[DISCOVERY] Connecting to: %s", bootstrap_addr_str)
    addr = Multiaddr(bootstrap_addr_str)
    peer_info = info_from_p2p_addr(addr)
    await host.connect(peer_info)
    logger.info("[DISCOVERY] Connected successfully")
