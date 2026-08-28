"""AgentPeer: a reusable py-libp2p peer.

This module owns everything that is genuinely "the P2P network" — starting
a libp2p host, connecting to other peers, opening/accepting streams on our
custom protocol. It deliberately knows nothing about LLMs, SeaLion, or
EtherCalc: that logic lives in agent.py / workflow.py / llm.py / ethercalc.py.

Built against the py-libp2p host API as documented in the project's own
chat example (`new_host`, `host.run(listen_addrs=...)` as an async context
manager alongside a trio nursery, `set_stream_handler`, `new_stream`,
`info_from_p2p_addr`). If you upgrade py-libp2p, diff this file against the
current `examples/chat/chat.py` in the py-libp2p repo before relying on it.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, Optional

import multiaddr
import trio
from libp2p import new_host
from libp2p.custom_types import TProtocol
from libp2p.network.stream.net_stream import INetStream
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.utils.address_validation import find_free_port, get_available_interfaces

from .messages import PROTOCOL_ID

logger = logging.getLogger(__name__)

StreamHandler = Callable[[INetStream], Awaitable[None]]


class AgentPeer:
    """A libp2p peer that speaks the /agent/task/1.0.0 protocol.

    Usage:

        peer = AgentPeer(port=8000)
        async with peer.start(on_stream=my_handler):
            addr = peer.listen_address()
            await peer.connect_to_peer(other_peer_multiaddr)
            stream = await peer.open_task_stream(other_peer_id)
            ...
    """

    def __init__(self, port: int = 0, protocol_id: str = PROTOCOL_ID) -> None:
        self.port = port if port > 0 else find_free_port()
        self.protocol_id = TProtocol(protocol_id)
        self._host = new_host()
        self._nursery: Optional[trio.Nursery] = None

    @property
    def peer_id(self) -> str:
        return str(self._host.get_id())

    def listen_addresses(self) -> list[str]:
        """Full multiaddresses (including /p2p/<peer-id>) others can dial."""
        return [str(a) for a in self._host.get_addrs()]

    @asynccontextmanager
    async def start(self, on_stream: Optional[StreamHandler] = None) -> AsyncIterator["AgentPeer"]:
        """Async context manager that brings the host + nursery up.

        `on_stream` is invoked for every *inbound* stream opened on our
        protocol ID (i.e. this peer acting as the responder/"Agent B").
        Callers acting purely as a requester ("Agent A") can omit it.

        Mirrors py-libp2p's own chat example pattern of nesting
        `host.run(...)` and `trio.open_nursery()` in a single `async with`
        statement, so trio's cancel-scope stack stays correctly ordered
        even under cancellation (e.g. Ctrl+C or a test timeout).
        """
        listen_addrs = get_available_interfaces(self.port)

        async with self._host.run(listen_addrs=listen_addrs), trio.open_nursery() as nursery:
            self._nursery = nursery
            nursery.start_soon(self._host.get_peerstore().start_cleanup_task, 60)

            if on_stream is not None:

                async def _handler(stream: INetStream) -> None:
                    try:
                        await on_stream(stream)
                    except Exception:  # noqa: BLE001 - never let a bad peer kill the host
                        logger.exception("Unhandled error in stream handler")

                self._host.set_stream_handler(self.protocol_id, _handler)

            logger.info("Peer %s listening at %s", self.peer_id, self.listen_addresses())
            try:
                yield self
            finally:
                nursery.cancel_scope.cancel()

    async def connect_to_peer(self, multiaddr_str: str) -> str:
        """Dial a peer by its full multiaddress. Returns the remote peer id."""
        info = info_from_p2p_addr(multiaddr.Multiaddr(multiaddr_str))
        await self._host.connect(info)
        return str(info.peer_id)

    async def open_task_stream(self, peer_id_str: str) -> INetStream:
        """Open an outbound stream to an already-connected peer."""
        from libp2p.peer.id import ID as PeerID

        peer_id = PeerID.from_base58(peer_id_str) if isinstance(peer_id_str, str) else peer_id_str
        return await self._host.new_stream(peer_id, [self.protocol_id])
