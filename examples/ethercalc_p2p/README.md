# P2PCalc — EtherCalc × py-libp2p PoC

> **Issue reference:** [seetadev/py-libp2p#34](https://github.com/seetadev/py-libp2p/issues/34)  
> **Status:** Proof of Concept (mid-point milestone scope)

Decentralised real-time spreadsheet collaboration by wiring
[EtherCalc](https://github.com/ether/ethercalc) to a
[py-libp2p](https://github.com/libp2p/py-libp2p) GossipSub mesh, replacing
the central Redis/WebSocket backend with a peer-to-peer network.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser                     Peer machine                        │
│  ┌──────────────┐            ┌──────────────────────────────┐   │
│  │  EtherCalc   │◄──WS────►│  adapter.py (WS bridge)      │   │
│  │  SocialCalc  │            │  ┌────────────────────────┐  │   │
│  │  UI          │            │  │  P2PCalcNode           │  │   │
│  └──────────────┘            │  │  • GossipSub pub-sub   │  │   │
│                              │  │  • mDNS discovery      │  │   │
│                              │  │  • LWW conflict res.   │  │   │
│                              │  └────────┬───────────────┘  │   │
│                              └───────────┼──────────────────┘   │
│                                          │ libp2p                │
│                              ┌───────────▼──────────────────┐   │
│                              │  Other peers (same topology) │   │
│                              └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key modules

| File | Role |
|---|---|
| `protocol.py` | Message schema — `SpreadsheetOp` JSON encoding |
| `sheet_state.py` | In-memory state with Last-Write-Wins conflict resolution |
| `p2p_node.py` | py-libp2p host, GossipSub, mDNS discovery |
| `adapter.py` | WebSocket bridge between EtherCalc and the p2p node |
| `demo.py` | Self-contained 3-peer demo (no EtherCalc needed) |

---

## Message Protocol

Every spreadsheet operation is serialised as JSON:

```json
{
  "op_id":    "9b1c…",
  "peer_id":  "<libp2p peer public key>",
  "timestamp": 1715000000.123,
  "sheet_id": "sheet-1",
  "op_type":  "SET_CELL",
  "payload":  { "cell": "A1", "value": "Revenue" }
}
```

Supported `op_type` values:

| Type | Payload keys |
|---|---|
| `SET_CELL` | `cell`, `value` |
| `SET_FORMULA` | `cell`, `formula` |
| `FORMAT_CELL` | `cell`, `format` (dict) |
| `INSERT_ROW` / `DELETE_ROW` | `row` |
| `INSERT_COL` / `DELETE_COL` | `col` |
| `REQUEST_STATE` | _(empty — sent by joining peer)_ |
| `STATE_SNAPSHOT` | `cells` (full cell map) |

### Conflict resolution (Phase 1 — LWW)

Concurrent edits to the same cell are resolved by **Last-Write-Wins**: the
message with the higher `timestamp` wins.  Duplicate `op_id`s are silently
dropped (idempotency guard).  A CRDT-based approach is planned for Phase 2.

---

## Quick Start

### 1. Install dependencies

```bash
pip install py-libp2p trio trio-websocket multiaddr
```

### 2. Run the standalone 3-peer demo

```bash
python -m examples.ethercalc_p2p.demo
```

Expected output (trimmed):

```
============================================================
  P2PCalc — Decentralised Spreadsheet PoC
  3-peer local simulation (mDNS + GossipSub)
============================================================

[demo] Starting nodes, waiting for mDNS discovery …
[demo] Publishing operations from each peer …

  [Peer-1] received SET_CELL  {'cell': 'A1', 'value': 'Revenue'}  from=<id>
  [Peer-2] received SET_CELL  {'cell': 'A1', 'value': 'Revenue'}  from=<id>
  ...

[demo] Final state on each peer:
  Peer-0 (bootstrap): A1=Revenue, B1=42000, C1==B1*0.18, D1=second
  Peer-1:             A1=Revenue, B1=42000, C1==B1*0.18, D1=second
  Peer-2:             A1=Revenue, B1=42000, C1==B1*0.18, D1=second

[demo] D1 conflict winner (LWW): second
[demo] All peers converged: ✓ YES
```

### 3. Run individual p2p nodes (interactive)

Terminal A (bootstrap node):
```bash
python -m examples.ethercalc_p2p.p2p_node
# Note the multiaddr printed, e.g.:
# /ip4/192.168.1.10/tcp/9100/p2p/12D3Koo…
```

Terminal B (connecting peer):
```bash
python -m examples.ethercalc_p2p.p2p_node -d /ip4/192.168.1.10/tcp/9100/p2p/12D3Koo…
```

Type `A1=Hello` and press Enter — it propagates to all peers instantly.

### 4. Connect EtherCalc (adapter mode)

Terminal A:
```bash
python -m examples.ethercalc_p2p.adapter --ws-port 8765 --p2p-port 9100
```

Terminal B:
```bash
python -m examples.ethercalc_p2p.adapter --ws-port 8766 --p2p-port 9101 \
  -d /ip4/127.0.0.1/tcp/9100/p2p/<PEER_A_ID>
```

Then apply the minimal EtherCalc patch (see `docs/ethercalc-patch.md`) to
forward SocialCalc commands to `ws://localhost:8765` instead of Redis.

---

## Roadmap / What's next

- [ ] CRDT vector clocks for causally-consistent conflict resolution
- [ ] Kademlia DHT peer discovery (cross-network)
- [ ] State snapshot transfer via libp2p streams (not GossipSub)
- [ ] IPFS persistence layer for durable snapshots
- [ ] Full EtherCalc WebSocket patch (no Redis dependency)
- [ ] Benchmark vs. centralised EtherCalc (latency, throughput)
- [ ] Dockerised multi-peer test environment

---

## Contributing

This is an active DMP 2026 project.  Issues and PRs are welcome — see the
[parent issue](https://github.com/seetadev/py-libp2p/issues/34) for the full
roadmap and mentors.
