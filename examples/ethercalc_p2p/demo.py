"""
Standalone multi-peer demo — no EtherCalc required.

Spawns 3 P2PCalcNode instances inside a single process using trio nurseries.
Peer-0 is the bootstrap; Peers 1 and 2 connect to it.

After all peers are connected the demo fires a series of cell-edit operations
from different peers and prints the resulting state on each node, showing that
all nodes converge to the same sheet.

Run:
    python -m examples.ethercalc_p2p.demo
"""

from __future__ import annotations

import logging
import sys

import trio

from .p2p_node import P2PCalcNode
from .protocol import set_cell, set_formula
from .sheet_state import SheetState

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Surface our own demo logs
_log = logging.getLogger("p2pcalc.demo")
_log.setLevel(logging.INFO)

SHEET = "demo-sheet"


def make_node(port: int = 0, bootstrap: str | None = None) -> P2PCalcNode:
    return P2PCalcNode(sheet_id=SHEET, port=port, bootstrap_addr=bootstrap)


async def run_demo() -> None:
    print("=" * 60)
    print("  P2PCalc — Decentralised Spreadsheet PoC")
    print("  3-peer local simulation (mDNS + GossipSub)")
    print("=" * 60)

    # We collect multiaddr of peer-0 after it starts
    peer0_addr: list[str] = []

    node0 = make_node(port=9100)
    node1 = make_node(port=9101)
    node2 = make_node(port=9102)

    nodes = [node0, node1, node2]
    labels = ["Peer-0 (bootstrap)", "Peer-1", "Peer-2"]

    update_counts = [0, 0, 0]

    for i, node in enumerate(nodes):
        idx = i

        def make_cb(label: str, counter_idx: int):
            def cb(op):
                update_counts[counter_idx] += 1
                print(
                    f"  [{label}] received {op.op_type}  "
                    f"{op.payload}  from={op.peer_id[:8]}"
                )
            return cb

        node.register_on_update(make_cb(labels[i], i))

    async with trio.open_nursery() as nursery:
        # Start all nodes
        for node in nodes:
            nursery.start_soon(node.run)

        # Let them boot and discover each other via mDNS
        print("\n[demo] Starting nodes, waiting for mDNS discovery …")
        await trio.sleep(6)

        print("\n[demo] Publishing operations from each peer …\n")

        # Peer-0 sets A1
        op0 = set_cell(node0._peer_id, SHEET, "A1", "Revenue")
        await node0.publish_op(op0)
        await trio.sleep(0.5)

        # Peer-1 sets B1
        op1 = set_cell(node1._peer_id, SHEET, "B1", "42000")
        await node1.publish_op(op1)
        await trio.sleep(0.5)

        # Peer-2 sets a formula
        op2 = set_formula(node2._peer_id, SHEET, "C1", "=B1*0.18")
        await node2.publish_op(op2)
        await trio.sleep(0.5)

        # Concurrent edit: Peer-0 and Peer-1 both write D1 (LWW resolves)
        import time
        op3a = set_cell(node0._peer_id, SHEET, "D1", "first")
        op3b = set_cell(node1._peer_id, SHEET, "D1", "second")
        # op3b is slightly newer
        op3b.timestamp = op3a.timestamp + 0.001
        await node0.publish_op(op3a)
        await node1.publish_op(op3b)
        await trio.sleep(1)

        print("\n[demo] Final state on each peer:")
        for label, node in zip(labels, nodes):
            state = node.get_state()
            cells = ", ".join(f"{k}={v}" for k, v in sorted(state.items()))
            print(f"  {label}: {cells if cells else '(empty)'}")

        print(
            "\n[demo] D1 conflict winner (LWW): "
            + (node0.get_state().get("D1") or "(not set)")
        )

        all_converged = all(
            n.get_state().get("A1") == "Revenue"
            and n.get_state().get("B1") == "42000"
            for n in nodes
        )
        print(
            "\n[demo] All peers converged: "
            + ("✓ YES" if all_converged else "✗ NO — check timing/connectivity")
        )

        print("\n[demo] Done. Shutting down.\n")
        nursery.cancel_scope.cancel()


def main() -> None:
    try:
        trio.run(run_demo)
    except* trio.Cancelled:
        pass
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
