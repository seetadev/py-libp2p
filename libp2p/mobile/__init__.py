"""
Mobile compatibility layer for py-libp2p.

This module provides mobile-compatible implementations of the libp2p transport layer,
designed to work with asyncio instead of trio for better mobile runtime support.
"""

from .runtime import AsyncRuntimeAdapter, is_mobile_runtime, get_runtime_adapter
from .transport import MobileTCPTransport, MobileTCPListener
from .io import MobileAsyncStream, MobileBufferedStream
from .factory import create_tcp_transport, get_transport_class

__all__ = [
    # Runtime adapter
    "AsyncRuntimeAdapter",
    "is_mobile_runtime", 
    "get_runtime_adapter",
    
    # Transport layer
    "MobileTCPTransport",
    "MobileTCPListener",
    
    # I/O layer
    "MobileAsyncStream",
    "MobileBufferedStream",
    
    # Factory functions
    "create_tcp_transport",
    "get_transport_class",
]
