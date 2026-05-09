"""
EtherCalc ↔ py-libp2p adapter (WebSocket bridge).

                ┌───────────────────────────────┐
  Browser       │         adapter.py             │
  EtherCalc  ←──┤  WebSocket  ←─  Outgoing msgs │
  UI         ──→┤  WebSocket  ─→  Incoming msgs  │
                │                                │
                │  P2PCalcNode (GossipSub)       │
                └───────────────────────────────┘

EtherCalc emits operation commands over its internal Redis channel (or
WebSocket when run in single-process mode).  This adapter taps those events,
converts them to ``SpreadsheetOp`` messages, and publishes them to the
libp2p GossipSub mesh.

For the PoC we expose a lightweight WebSocket endpoint on
``ws://localhost:8765`` that EtherCalc can be patched to forward commands
to.  Full EtherCalc hook integration is tracked in a follow-up milestone.

Run:
    python -m examples.ethercalc_p2p.adapter --port 8765 --p2p-port 9000

then point your EtherCalc patch at ws://localhost:8765.
"""

from __future__ import annotations

import argparse
import json
import logging
import re

import trio
import trio_websocket  # pip install trio-websocket

from .p2p_node import P2PCalcNode
from .protocol import (
    OpType,
    SpreadsheetOp,
    format_cell,
    set_cell,
    set_formula,
)

logger = logging.getLogger(__name__)

DEFAULT_SHEET = "sheet-1"

# ---- EtherCalc command parser ----
# EtherCalc uses the SocialCalc "command" protocol over its WebSocket.
# A typical SET command looks like:  set A1 value n 42
# A formula command looks like:      set A1 formula =SUM(B1:B10)
_SET_RE = re.compile(
    r"^set\s+(?P<cell>[A-Z]+\d+)\s+(?P<type>value|formula|text)\s+(?P<rest>.+)$",
    re.IGNORECASE,
)


def ethercalc_cmd_to_op(
    peer_id: str, sheet_id: str, cmd: str
) -> SpreadsheetOp | None:
    """
    Convert a SocialCalc command string to a ``SpreadsheetOp``.
    Returns None for unrecognised commands (they are logged and dropped).
    """
    m = _SET_RE.match(cmd.strip())
    if not m:
        logger.debug("Unrecognised EtherCalc command: %r", cmd)
        return None

    cell = m.group("cell").upper()
    kind = m.group("type").lower()
    rest = m.group("rest").strip()

    if kind == "formula":
        return set_formula(peer_id, sheet_id, cell, rest)
    else:
        # Strip SocialCalc type prefix (e.g. "n 42" → "42", "t Hello" → "Hello")
        value = rest.split(" ", 1)[-1] if " " in rest else rest
        return set_cell(peer_id, sheet_id, cell, value)


def op_to_ethercalc_cmd(op: SpreadsheetOp) -> str | None:
    """Convert an incoming ``SpreadsheetOp`` back to a SocialCalc command string."""
    if op.op_type == OpType.SET_CELL.value:
        cell = op.payload.get("cell", "")
        value = op.payload.get("value", "")
        # Emit as text type; EtherCalc will reparse
        return f"set {cell} value t {value}"
    if op.op_type == OpType.SET_FORMULA.value:
        cell = op.payload.get("cell", "")
        formula = op.payload.get("formula", "")
        return f"set {cell} formula {formula}"
    return None


# ---- WebSocket server ----

async def ws_handler(ws_request, node: P2PCalcNode) -> None:
    ws = await ws_request.accept()
    remote = ws_request.remote

    logger.info("EtherCalc client connected: %s", remote)

    # Push new remote ops to this WebSocket
    outbox: list[str] = []

    def on_update(op: SpreadsheetOp) -> None:
        cmd = op_to_ethercalc_cmd(op)
        if cmd:
            outbox.append(cmd)

    node.register_on_update(on_update)

    async with trio.open_nursery() as nursery:
        async def sender():
            while True:
                if outbox:
                    cmd = outbox.pop(0)
                    await ws.send_message(cmd)
                else:
                    await trio.sleep(0.05)

        async def receiver():
            while True:
                try:
                    raw = await ws.get_message()
                    logger.debug("← EtherCalc: %r", raw)
                    op = ethercalc_cmd_to_op(node._peer_id, node.sheet_id, raw)
                    if op:
                        await node.publish_op(op)
                except trio_websocket.ConnectionClosed:
                    logger.info("EtherCalc client disconnected: %s", remote)
                    nursery.cancel_scope.cancel()
                    break

        nursery.start_soon(sender)
        nursery.start_soon(receiver)


async def run_adapter(ws_port: int, p2p_port: int, bootstrap: str | None) -> None:
    node = P2PCalcNode(port=p2p_port, bootstrap_addr=bootstrap)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(node.run)
        # Give the node a moment to initialize before accepting WebSocket connections
        await trio.sleep(1)

        logger.info("Adapter WebSocket listening on ws://localhost:%d", ws_port)
        await trio_websocket.serve_websocket(
            lambda req: ws_handler(req, node),
            host="localhost",
            port=ws_port,
            ssl_context=None,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="EtherCalc ↔ py-libp2p adapter")
    parser.add_argument("--ws-port", type=int, default=8765,
                        help="WebSocket port for EtherCalc to connect to")
    parser.add_argument("--p2p-port", type=int, default=0,
                        help="libp2p listening port")
    parser.add_argument("-d", "--destination", type=str, default=None,
                        help="Bootstrap peer multiaddr")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        trio.run(run_adapter, args.ws_port, args.p2p_port, args.destination)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
