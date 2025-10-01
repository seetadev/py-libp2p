"""
Transport factory for choosing between trio and mobile implementations.

This module provides a factory that automatically chooses the appropriate
transport implementation based on the runtime environment.
"""

from typing import Type

from libp2p.abc import ITransport
from libp2p.mobile.runtime import is_mobile_runtime, get_runtime_adapter
from libp2p.mobile.transport import MobileTCPTransport


def create_tcp_transport() -> ITransport:
    """
    Create a TCP transport appropriate for the current runtime.
    
    Returns:
        ITransport: MobileTCPTransport for mobile, or original TCP for desktop
    """
    runtime_adapter = get_runtime_adapter()
    
    if runtime_adapter.use_asyncio or is_mobile_runtime():
        # Use mobile-compatible transport
        return MobileTCPTransport()
    else:
        # Use original trio-based transport for desktop
        try:
            from libp2p.transport.tcp.tcp import TCP
            return TCP()
        except ImportError:
            # Fallback to mobile transport if trio is not available
            return MobileTCPTransport()


def get_transport_class() -> Type[ITransport]:
    """
    Get the transport class appropriate for the current runtime.
    
    Returns:
        Type[ITransport]: Transport class to use
    """
    runtime_adapter = get_runtime_adapter()
    
    if runtime_adapter.use_asyncio or is_mobile_runtime():
        return MobileTCPTransport
    else:
        try:
            from libp2p.transport.tcp.tcp import TCP
            return TCP
        except ImportError:
            return MobileTCPTransport
