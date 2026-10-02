from abc import ABC, abstractmethod
from py_libp2p.utils.network import parse_multiaddr, Multiaddr

class Transport(ABC):
    """
    Abstract Base Class for Transports.
    Now natively uses Multiaddr for address handling.
    """
    
    @abstractmethod
    async def listen(self, addr: Multiaddr):
        """Start listening on the given multiaddr."""
        pass

    @abstractmethod
    async def connect(self, addr: Multiaddr):
        """Connect to the given multiaddr."""
        pass

    def validate_address(self, addr: str) -> Multiaddr:
        """Utility to validate and parse addresses before transport use."""
        return parse_multiaddr(addr)
