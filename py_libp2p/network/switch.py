from typing import Dict, Any
from py_libp2p.utils.network import parse_multiaddr, Multiaddr, format_multiaddr

class Switch:
    """
    The Switch manages connections and protocol negotiation.
    Updated to handle Multiaddr objects consistently.
    """
    def __init__(self):
        self.connections: Dict[str, Any] = {}

    async def add_connection(self, peer_id: str, addr: Union[str, Multiaddr], connection: Any):
        # Normalize address to Multiaddr object internally
        maddr = parse_multiaddr(addr)
        conn_key = f"{peer_id}:{format_multiaddr(maddr)}"
        self.connections[conn_key] = {
            "address": maddr,
            "connection": connection,
            "peer_id": peer_id
        }

    def get_connection_by_addr(self, addr: Union[str, Multiaddr]):
        maddr = parse_multiaddr(addr)
        for key, val in self.connections.items():
            if val["address"] == maddr:
                return val["connection"]
        return None
