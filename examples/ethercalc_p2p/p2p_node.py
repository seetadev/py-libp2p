"""
P2PCalc py-libp2p node.

Starts a libp2p host with:
  • GossipSub pub-sub on the ``spreadsheet-updates`` topic
  • mDNS peer discovery (LAN)
  • Automatic connection to a bootstrap peer (optional, for cross-network)

Incoming operations are applied to a local ``SheetState`` and forwarded to
any registered ``on_update`` callbacks so the adapter layer can push them
into the EtherCalc WebSocket bridge.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import secrets
from typing import Callable

import trio

from libp2p import new_host
from libp2p.abc import PeerInfo
from libp2p.crypto.secp256k1 import create_new_key_pair
from libp2p.custom_types import TProtocol
from libp2p.discovery.events.peerDiscovery import peerDiscovery
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.stream_muxer.mplex.mplex import MPLEX_PROTOCOL_ID, Mplex
from libp2p.tools.anyio_service import background_trio_service
from libp2p.utils.address_validation import find_free_port, get_available_interfaces

import multiaddr

from .protocol import OpType, SpreadsheetOp, request_state, state_snapshot
from .sheet_state import SheetState

logger = logging.getLogger(__name__)

TOPIC = "spreadsheet-updates"
GOSSIPSUB_PROTO = TProtocol("/meshsub/1.0.0")
DEFAULT_SHEET = "sheet-1"


class P2PCalcNode:
    """
    A single py-libp2p peer that participates in decentralised spreadsheet
    collaboration.  Instantiate it, register ``on_update`` callbacks, then
    call ``run()`` inside a trio event loop.
    """

    def __init__(
        self,
        sheet_id: str = DEFAULT_SHEET,
        port: int = 0,
        bootstrap_addr: str | None = None,
    ) -> None:
        self.sheet_id = sheet_id
        self.port = port or find_free_port()
        self.bootstrap_addr = bootstrap_addr

        secret = secrets.token_bytes(32)
        self._key_pair = create_new_key_pair(secret)
        self._state = SheetState(sheet_id)
        self._on_update_cbs: list[Callable[[SpreadsheetOp], None]] = []
        self._pubsub: Pubsub | None = None
        self._peer_id: str = ""

    # ---- public API ----

    def register_on_update(self, cb: Callable[[SpreadsheetOp], None]) -> None:
        """Register a callback invoked whenever remote state changes."""
        self._on_update_cbs.append(cb)

    def get_state(self) -> dict[str, str]:
        return self._state.snapshot()

    async def publish_op(self, op: SpreadsheetOp) -> None:
        """Publish a locally-originating spreadsheet operation to all peers."""
        if self._pubsub is None:
            raise RuntimeError("Node not running")
        self._state.apply(op)
        await self._pubsub.publish(TOPIC, op.encode())

    async def run(self) -> None:
        listen_addrs = get_available_interfaces(self.port)

        host = new_host(
            key_pair=self._key_pair,
            muxer_opt={MPLEX_PROTOCOL_ID: Mplex},
            enable_mDNS=True,
        )
        self._peer_id = host.get_id().to_string()

        gossipsub = GossipSub(
            protocols=[GOSSIPSUB_PROTO],
            degree=3,
            degree_low=2,
            degree_high=4,
            time_to_live=60,
            gossip_window=2,
            gossip_history=5,
            heartbeat_initial_delay=2.0,
            heartbeat_interval=5,
        )
        self._pubsub = Pubsub(host, gossipsub)

        # Register mDNS discovery handler
        peerDiscovery.register_peer_discovered_handler(
            lambda info: trio.from_thread.run_sync(
                lambda: logger.info("mDNS discovered: %s", info.peer_id)
            )
            if False
            else logger.info("mDNS discovered: %s", info.peer_id)
        )

        async with host.run(listen_addrs=listen_addrs), trio.open_nursery() as nursery:
            nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)

            logger.info("P2PCalc node started  peer_id=%s", self._peer_id[:12])
            for addr in host.get_addrs():
                logger.info("  listening on %s", addr)

            async with background_trio_service(self._pubsub):
                async with background_trio_service(gossipsub):
                    await self._pubsub.wait_until_ready()
                    subscription = await self._pubsub.subscribe(TOPIC)
                    logger.info("Subscribed to topic: %s", TOPIC)

                    if self.bootstrap_addr:
                        await self._connect_bootstrap(host)

                    # Announce ourselves and ask for current state
                    req = request_state(self._peer_id, self.sheet_id)
                    await self._pubsub.publish(TOPIC, req.encode())

                    nursery.start_soon(self._receive_loop, subscription)

    # ---- internal ----

    async def _connect_bootstrap(self, host) -> None:
        try:
            maddr_obj = multiaddr.Multiaddr(self.bootstrap_addr)
            info = info_from_p2p_addr(maddr_obj)
            await host.connect(info)
            logger.info("Connected to bootstrap peer: %s", info.peer_id)
        except Exception:
            logger.exception("Failed to connect to bootstrap peer")

    async def _receive_loop(self, subscription) -> None:
        while True:
            try:
                msg = await subscription.get()
                raw_peer = msg.from_id
                op = SpreadsheetOp.decode(msg.data)

                # Don't process our own re-echoed messages
                if op.peer_id == self._peer_id:
                    continue

                if op.op_type == OpType.REQUEST_STATE.value:
                    # A peer just joined — send them our current snapshot
                    snap = state_snapshot(
                        self._peer_id, self.sheet_id, self._state.snapshot()
                    )
                    await self._pubsub.publish(TOPIC, snap.encode())
                    continue

                changed = self._state.apply(op)
                if changed:
                    for cb in self._on_update_cbs:
                        try:
                            cb(op)
                        except Exception:
                            logger.exception("on_update callback raised")
            except Exception:
                logger.exception("Error in receive loop")
                await trio.sleep(1)


# ---- standalone CLI for quick testing ----

async def _main(port: int, bootstrap: str | None) -> None:
    node = P2PCalcNode(port=port, bootstrap_addr=bootstrap)

    def on_update(op: SpreadsheetOp) -> None:
        print(f"[REMOTE] {op.op_type}  {op.payload}  from={op.peer_id[:8]}")

    node.register_on_update(on_update)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(node.run)
        # Interactive publish loop
        while True:
            try:
                line = await trio.to_thread.run_sync(
                    lambda: input("cell=value (e.g. A1=Hello): ")
                )
                if not line.strip():
                    continue
                if "=" not in line:
                    print("Format: <CELL>=<VALUE>")
                    continue
                cell, value = line.split("=", 1)
                from .protocol import set_cell
                op = set_cell(node._peer_id, DEFAULT_SHEET, cell.strip(), value.strip())
                await node.publish_op(op)
            except KeyboardInterrupt:
                nursery.cancel_scope.cancel()
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="P2PCalc node (standalone demo)")
    parser.add_argument("-p", "--port", type=int, default=0)
    parser.add_argument("-d", "--destination", type=str, default=None,
                        help="Multiaddr of bootstrap peer")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        trio.run(_main, args.port, args.destination)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
