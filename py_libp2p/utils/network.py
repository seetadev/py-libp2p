from multiaddr import Multiaddr
from typing import Union, List

class MultiaddrError(Exception):
    """Custom exception for multiaddr parsing and validation errors."""
    pass

def parse_multiaddr(address: Union[str, Multiaddr]) -> Multiaddr:
    """
    Ensures the given address is a Multiaddr object.
    """
    if isinstance(address, Multiaddr):
        return address
    try:
        return Multiaddr(address)
    except Exception as e:
        raise MultiaddrError(f"Invalid multiaddr format: {address}. Error: {str(e)}")

def format_multiaddr(address: Union[str, Multiaddr]) -> str:
    """
    Ensures the given address is returned as a string.
    """
    if isinstance(address, Multiaddr):
        return str(address)
    return address

def extract_peer_id(address: Union[str, Multiaddr]) -> Union[str, None]:
    """
    Extracts the peer ID from a multiaddr if present (/p2p/...).
    """
    maddr = parse_multiaddr(address)
    # Multiaddr components are stored as a list of protocols and values
    # We look for the /p2p/ protocol
    for i in range(len(maddr.protocols)):
        if maddr.protocols[i] == 4: # 4 is the code for p2p
            return maddr.values[i]
    return None
