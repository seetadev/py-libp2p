"""
Async runtime adapter for mobile compatibility.

This module provides an abstraction layer that allows py-libp2p to work with
different async runtimes (trio for desktop, asyncio for mobile).
"""

import sys
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Callable, Coroutine, TypeVar, Awaitable
from collections.abc import AsyncIterator

T = TypeVar('T')

# Optional trio import
try:
    import trio
    HAS_TRIO = True
except ImportError:
    HAS_TRIO = False
    trio = None


def is_mobile_runtime() -> bool:
    """
    Detect if running on a mobile platform.
    
    Returns:
        bool: True if running on Android, iOS, or in a WASM environment (Pyodide)
    """
    return (
        hasattr(sys, 'getandroidapilevel') or  # Android
        sys.platform == 'ios' or               # iOS  
        'pyodide' in sys.modules or            # Pyodide/WASM
        'androidsdk' in sys.modules            # Python-for-Android
    )


class AsyncRuntimeAdapter:
    """
    Adapter that provides a unified interface for different async runtimes.
    
    On mobile platforms, uses asyncio. On desktop, can use trio or asyncio.
    """
    
    def __init__(self, force_asyncio: bool = False):
        """
        Initialize the runtime adapter.
        
        Args:
            force_asyncio: If True, force use of asyncio even on desktop
        """
        self.use_asyncio = force_asyncio or is_mobile_runtime()
        
        if self.use_asyncio:
            self.runtime_name = 'asyncio'
        else:
            if HAS_TRIO:
                self.runtime_name = 'trio'
            else:
                # Fallback to asyncio if trio is not available
                self.use_asyncio = True
                self.runtime_name = 'asyncio'
    
    @asynccontextmanager
    async def create_nursery(self) -> AsyncIterator['MobileNursery']:
        """
        Create a nursery/task group for concurrent task execution.
        
        Yields:
            MobileNursery: A nursery object that can spawn tasks
        """
        if self.use_asyncio:
            # Use TaskGroup for Python 3.11+, fallback for older versions
            try:
                async with asyncio.TaskGroup() as task_group:
                    yield AsyncioNursery(task_group)
            except AttributeError:
                # Fallback for Python < 3.11
                nursery = AsyncioNurseryLegacy()
                try:
                    yield nursery
                finally:
                    await nursery.close()
        else:
            if HAS_TRIO and trio is not None:
                async with trio.open_nursery() as nursery:
                    yield TrioNursery(nursery)
            else:
                # Fallback if trio is not available
                nursery = AsyncioNurseryLegacy()
                try:
                    yield nursery
                finally:
                    await nursery.close()
    
    async def start_task(self, func: Callable[..., Awaitable[T]], *args: Any) -> T:
        """
        Start a task and return when it completes.
        
        Args:
            func: Async function to run
            *args: Arguments to pass to the function
            
        Returns:
            The result of the function
        """
        if self.use_asyncio:
            return await func(*args)
        else:
            import trio
            return await func(*args)


class MobileNursery:
    """Base class for nursery implementations."""
    
    async def start_soon(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
        """Start a task without waiting for it to complete."""
        raise NotImplementedError


class AsyncioNursery(MobileNursery):
    """Nursery implementation using asyncio.TaskGroup (Python 3.11+)."""
    
    def __init__(self, task_group: asyncio.TaskGroup):
        self.task_group = task_group
    
    async def start_soon(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
        """Start a task in the task group."""
        coro = func(*args)
        self.task_group.create_task(coro)


class AsyncioNurseryLegacy(MobileNursery):
    """Nursery implementation for older Python versions without TaskGroup."""
    
    def __init__(self):
        self.tasks: list[asyncio.Task] = []
    
    async def start_soon(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
        """Start a task and track it."""
        coro = func(*args)
        task = asyncio.create_task(coro)
        self.tasks.append(task)
    
    async def close(self) -> None:
        """Wait for all tasks to complete."""
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)


class TrioNursery(MobileNursery):
    """Nursery implementation using trio."""
    
    def __init__(self, nursery):
        self.nursery = nursery
    
    async def start_soon(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
        """Start a task in the trio nursery."""
        if HAS_TRIO and trio:
            self.nursery.start_soon(func, *args)
        else:
            # This shouldn't happen if trio is available, but just in case
            raise RuntimeError("Trio nursery not available")


# Global runtime adapter instance
_runtime_adapter = AsyncRuntimeAdapter()


def get_runtime_adapter() -> AsyncRuntimeAdapter:
    """Get the global runtime adapter instance."""
    return _runtime_adapter


def set_runtime_adapter(adapter: AsyncRuntimeAdapter) -> None:
    """Set a custom runtime adapter."""
    global _runtime_adapter
    _runtime_adapter = adapter
