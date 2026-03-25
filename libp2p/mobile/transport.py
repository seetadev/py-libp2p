"""
Mobile-compatible transport implementations for py-libp2p.

This module provides asyncio-based transport implementations that can run
on mobile platforms while maintaining compatibility with the existing
trio-based desktop implementation.
"""

import asyncio
import logging
import socket
from typing import Any, Callable, Optional, Sequence
from collections.abc import Awaitable

from multiaddr import Multiaddr

from libp2p.abc import IListener, IRawConnection, ITransport
from libp2p.custom_types import THandler
from libp2p.network.connection.raw_connection import RawConnection
from libp2p.transport.exceptions import OpenConnectionError
from .runtime import get_runtime_adapter, MobileNursery
from libp2p.mobile.io import MobileAsyncStream

logger = logging.getLogger("libp2p.mobile.transport")


class MobileTCPListener(IListener):
    """
    Mobile-compatible TCP listener using asyncio.
    
    This listener can coexist with the trio-based TCP listener and provides
    the same interface while using asyncio for mobile compatibility.
    """
    
    def __init__(self, handler_function: THandler) -> None:
        self.handler = handler_function
        self.servers: list[asyncio.Server] = []
        self.addresses: list[Multiaddr] = []
        self._runtime_adapter = get_runtime_adapter()
    
    async def listen(self, maddr: Multiaddr, nursery: Any) -> bool:
        """
        Start listening on the specified multiaddress.
        
        Args:
            maddr: The multiaddress to listen on
            nursery: Nursery for task management (can be trio or mobile nursery)
            
        Returns:
            True if listening started successfully, False otherwise
        """
        tcp_port_str = maddr.value_for_protocol("tcp")
        if tcp_port_str is None:
            logger.error(f"Cannot listen: TCP port is missing in multiaddress {maddr}")
            return False

        try:
            tcp_port = int(tcp_port_str)
        except ValueError:
            logger.error(
                f"Cannot listen: Invalid TCP port '{tcp_port_str}' "
                f"in multiaddress {maddr}"
            )
            return False

        ip4_host_str = maddr.value_for_protocol("ip4")
        # None means listen on all interfaces
        host = ip4_host_str or "0.0.0.0"
        
        try:
            if self._runtime_adapter.use_asyncio:
                await self._start_asyncio_server(host, tcp_port, nursery)
            else:
                # Fallback to trio behavior for compatibility
                await self._start_with_nursery(host, tcp_port, nursery)
                
            # Store the address we're actually listening on
            actual_addr = f"/ip4/{host}/tcp/{tcp_port}"
            self.addresses.append(Multiaddr(actual_addr))
            
            logger.info(f"Mobile TCP listener started on {actual_addr}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start TCP listener for {maddr}: {e}")
            return False
    
    async def _start_asyncio_server(self, host: str, port: int, nursery: Any) -> None:
        """Start server using asyncio."""
        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            """Handle incoming client connection."""
            try:
                stream = MobileAsyncStream(reader, writer)
                await self.handler(stream)
            except Exception as e:
                logger.debug(f"Connection handling failed: {e}")
                if not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()
        
        server = await asyncio.start_server(handle_client, host, port)
        self.servers.append(server)
        
        # Start serving in the background
        if hasattr(nursery, 'start_soon'):
            # This is our mobile nursery
            await nursery.start_soon(server.serve_forever)
        else:
            # Start serving in background task
            asyncio.create_task(server.serve_forever())
    
    async def _start_with_nursery(self, host: str, port: int, nursery: Any) -> None:
        """Start server using nursery (trio compatibility)."""
        # For trio compatibility when not in mobile mode
        # This would delegate to the original trio implementation
        # For now, fallback to asyncio
        await self._start_asyncio_server(host, port, nursery)
    
    def get_addrs(self) -> tuple[Multiaddr, ...]:
        """
        Get the addresses this listener is bound to.
        
        Returns:
            Tuple of multiaddresses
        """
        return tuple(self.addresses)
    
    async def close(self) -> None:
        """Close all servers and clean up."""
        for server in self.servers:
            server.close()
            await server.wait_closed()
        self.servers.clear()
        self.addresses.clear()


class MobileTCPTransport(ITransport):
    """
    Mobile-compatible TCP transport using asyncio.
    
    This transport can coexist with the trio-based TCP transport and provides
    the same interface while using asyncio for mobile compatibility.
    """
    
    def __init__(self) -> None:
        self._runtime_adapter = get_runtime_adapter()
    
    async def dial(self, maddr: Multiaddr) -> IRawConnection:
        """
        Dial a peer on the specified multiaddress.
        
        Args:
            maddr: The multiaddress of the peer to dial
            
        Returns:
            IRawConnection: The established connection
            
        Raises:
            OpenConnectionError: If the connection cannot be established
        """
        host_str = maddr.value_for_protocol("ip4")
        port_str = maddr.value_for_protocol("tcp")

        if host_str is None:
            raise OpenConnectionError(
                f"Failed to dial {maddr}: IP address not found in multiaddr."
            )

        if port_str is None:
            raise OpenConnectionError(
                f"Failed to dial {maddr}: TCP port not found in multiaddr."
            )

        try:
            port_int = int(port_str)
        except ValueError:
            raise OpenConnectionError(
                f"Failed to dial {maddr}: Invalid TCP port '{port_str}'."
            )

        try:
            if self._runtime_adapter.use_asyncio:
                # Use asyncio for mobile compatibility
                reader, writer = await asyncio.open_connection(host_str, port_int)
                stream = MobileAsyncStream(reader, writer)
            else:
                # Fallback to trio behavior for desktop compatibility
                # In a real implementation, this would use the original trio transport
                # For now, we'll use asyncio as fallback
                reader, writer = await asyncio.open_connection(host_str, port_int)
                stream = MobileAsyncStream(reader, writer)
                
            return RawConnection(stream, True)  # True indicates we initiated the connection
            
        except OSError as error:
            raise OpenConnectionError(
                f"Failed to open TCP stream to {maddr}: {error}"
            ) from error
        except Exception as error:
            raise OpenConnectionError(
                f"An unexpected error occurred when dialing {maddr}: {error}"
            ) from error
    
    def create_listener(self, handler_function: THandler) -> MobileTCPListener:
        """
        Create a mobile-compatible TCP listener.
        
        Args:
            handler_function: Function to handle incoming connections
            
        Returns:
            MobileTCPListener: The created listener
        """
        return MobileTCPListener(handler_function)


def _multiaddr_from_socket_info(host: str, port: int) -> Multiaddr:
    """Create a multiaddr from host and port information."""
    return Multiaddr(f"/ip4/{host}/tcp/{port}")
