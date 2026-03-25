"""
Mobile-compatible I/O stream implementations.

This module provides asyncio-based stream implementations that are compatible
with mobile platforms while maintaining the same interface as the trio-based
implementations.
"""

import asyncio

from libp2p.io.abc import ReadWriteCloser


class MobileAsyncStream(ReadWriteCloser):
    """
    Mobile-compatible stream implementation using asyncio.
    
    This provides the same interface as TrioTCPStream but uses asyncio
    StreamReader and StreamWriter for mobile compatibility.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False
    
    async def read(self, n: int | None = None) -> bytes:
        """
        Read up to n bytes from the stream.
        
        Args:
            n: Maximum number of bytes to read. If None, read until EOF.
            
        Returns:
            bytes: The data read from the stream
            
        Raises:
            Exception: If the stream is closed or an error occurs
        """
        if self._closed:
            raise Exception("Stream is closed")
        
        try:
            if n is None:
                # Read until EOF
                return await self.reader.read()
            else:
                # Read exactly n bytes or until EOF
                return await self.reader.read(n)
        except Exception as e:
            await self.close()
            raise e
    
    async def write(self, data: bytes) -> None:
        """
        Write data to the stream.
        
        Args:
            data: The data to write
            
        Raises:
            Exception: If the stream is closed or an error occurs
        """
        if self._closed:
            raise Exception("Stream is closed")
        
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            await self.close()
            raise e
    
    async def close(self) -> None:
        """
        Close the stream and clean up resources.
        """
        if not self._closed:
            self._closed = True
            
            if not self.writer.is_closing():
                self.writer.close()
                try:
                    await self.writer.wait_closed()
                except Exception:
                    # Ignore errors during close
                    pass
    
    def get_remote_address(self) -> tuple[str, int] | None:
        """
        Return the remote address of the connected peer.
        
        Returns:
            tuple[str, int] | None: (host, port) tuple or None if not available
        """
        try:
            peername = self.writer.get_extra_info('peername')
            if peername and len(peername) >= 2:
                return (str(peername[0]), int(peername[1]))
        except Exception:
            pass
        return None
    
    def get_local_address(self) -> tuple[str, int] | None:
        """
        Get the local address of the connection.
        
        Returns:
            tuple[str, int] | None: (host, port) tuple or None if not available
        """
        try:
            sockname = self.writer.get_extra_info('sockname')
            if sockname and len(sockname) >= 2:
                return (str(sockname[0]), int(sockname[1]))
        except Exception:
            pass
        return None
    
    @property
    def closed(self) -> bool:
        """
        Check if the stream is closed.
        
        Returns:
            bool: True if the stream is closed
        """
        return self._closed or self.writer.is_closing()


class MobileBufferedStream(MobileAsyncStream):
    """
    Buffered version of MobileAsyncStream for improved performance.
    
    This adds buffering capabilities for scenarios where frequent small
    reads/writes might impact performance on mobile devices.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, 
                 read_buffer_size: int = 8192, write_buffer_size: int = 8192):
        super().__init__(reader, writer)
        self._read_buffer_size = read_buffer_size
        self._write_buffer_size = write_buffer_size
        self._write_buffer = bytearray()
    
    async def write(self, data: bytes) -> None:
        """
        Buffered write operation.
        
        Args:
            data: The data to write
        """
        if self._closed:
            raise Exception("Stream is closed")
        
        self._write_buffer.extend(data)
        
        # Flush if buffer is full
        if len(self._write_buffer) >= self._write_buffer_size:
            await self.flush()
    
    async def flush(self) -> None:
        """
        Flush the write buffer to the underlying stream.
        """
        if self._closed:
            raise Exception("Stream is closed")
        
        if self._write_buffer:
            try:
                self.writer.write(bytes(self._write_buffer))
                await self.writer.drain()
                self._write_buffer.clear()
            except Exception as e:
                await self.close()
                raise e
    
    async def close(self) -> None:
        """
        Close the stream, flushing any remaining buffered data.
        """
        if not self._closed:
            try:
                # Flush remaining data before closing
                await self.flush()
            except Exception:
                # Ignore flush errors during close
                pass
            
            await super().close()
