# Decentralized Federated Learning over py-libp2p

A minimal decentralized federated-learning prototype demonstrating
local model training, peer-to-peer model-update exchange, and
decentralized FedAvg using [py-libp2p](https://github.com/libp2p/py-libp2p).

Multiple independent peers train the same logistic regression model
on their own local (non-IID) data and exchange only model
**parameters** over a custom libp2p protocol — never raw training
data — with no central aggregation server. Every peer independently
runs the same FedAvg aggregation on the updates it collects, so no
single peer acts as a coordinator.

> Target issue: `py-libp2p #4`

## Architecture

```
                        ┌─────────────────────┐
                        │   P2P Network        │
                        │ /ml/federated-       │
                        │ learning/1.0.0        │
                        └──────────┬──────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
  │   PEER A    │◄─────────►│   PEER B    │◄─────────►│   PEER C    │
  ├─────────────┤           ├─────────────┤           ├─────────────┤
  │ Local Data  │           │ Local Data  │           │ Local Data  │
  │     ↓       │           │     ↓       │           │     ↓       │
  │ Local Model │           │ Local Model │           │ Local Model │
  │     ↓       │           │     ↓       │           │     ↓       │
  │ Train       │           │ Train       │           │ Train       │
  │     ↓       │           │     ↓       │           │     ↓       │
  │ Update A    │           │ Update B    │           │ Update C    │
  └──────┬──────┘           └──────┬──────┘           └──────┬──────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   ▼
                             Local FedAvg
                                   │
                                   ▼
                             New Model
                                   │
                                   ▼
                             Next Round
```

Each peer independently derives the same global model from the
updates it has received — decentralized, not client-server.

## Project structure

```
p2p-federated-learning/
│
├── README.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
│
├── federated_learning/
│   ├── __init__.py
│   ├── model.py           # LogisticRegression parameter get/set
│   ├── dataset.py          # non-IID synthetic dataset + sharding
│   ├── aggregation.py       # FedAvg (sample-count weighted)
│   ├── serialization.py     # ModelUpdate <-> newline-delimited JSON
│   ├── protocol.py          # /ml/federated-learning/1.0.0 + validation
│   ├── peer.py              # FederatedPeer: networking + FL loop
│   └── training.py          # local train/evaluate
│
├── run_peer.py              # CLI entry point
│
├── tests/
│   ├── test_model.py
│   ├── test_aggregation.py
│   ├── test_serialization.py
│   ├── test_protocol.py
│   └── test_p2p.py          # real libp2p integration test
│
└── examples/
    └── demo.md
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.10+.

## Usage

**Terminal 1:**
```bash
python run_peer.py --port 8000 --peer-index 0 --n-peers 2
```
This prints a peer ID and listening multiaddr, e.g.
`/ip4/127.0.0.1/tcp/8000/p2p/12D3KooW...`.

**Terminal 2:**
```bash
python run_peer.py --port 8001 --peer-index 1 --n-peers 2 \
    --peers /ip4/127.0.0.1/tcp/8000/p2p/12D3KooW...
```

Both peers train locally, exchange `ModelUpdate` messages over the
custom protocol, aggregate via sample-weighted FedAvg, and print
local vs. federated accuracy per round.

See `examples/demo.md` for a 3-peer walkthrough and sample output.

### CLI arguments

| Flag | Description |
|---|---|
| `--port` | TCP port to listen on (required) |
| `--peers` | Comma-separated multiaddrs to connect to on startup |
| `--peer-index` | Which non-IID data shard this peer uses |
| `--n-peers` | Total peers in this run (dataset sharding only) |
| `--expected-peers` | Peers to wait for updates from each round (defaults to `len(--peers)`) |
| `--rounds` | Number of training rounds (default 3) |
| `--samples` | Total synthetic dataset size before sharding (default 900) |
| `--features` | Number of features (default 10) |
| `--seed` | Random seed |
| `--round-timeout` | Seconds to wait for peer updates before aggregating with what arrived (default 60) |
| `--verbose` | Enable debug logging |

## Running tests

```bash
pytest
```

`tests/test_p2p.py` spins up two real libp2p hosts on localhost —
no mocking of the network layer.

## What gets sent over the wire

Only this, as newline-delimited JSON:

```json
{
  "type": "model_update",
  "peer_id": "12D3Koo...",
  "round": 1,
  "num_samples": 300,
  "weights": [[0.21, -0.31, 0.72]],
  "bias": [0.15]
}
```

Raw `X_train` / `y_train` never leave `training.py` and are never
passed to `serialization.py` or `protocol.py`.

## Privacy note

This prototype provides **data locality** — raw training data stays
on the peer that generated it. It does **not** provide strong privacy
guarantees: model updates can still leak information about the
underlying data. Additional techniques such as differential privacy
or secure aggregation would be required for stronger guarantees.

## Limitations

- Bootstrapping is manual: a peer only waits for updates from peers
  it knows about via `--peers`/`--expected-peers`. There's no
  automatic peer discovery yet (would need GossipSub or a DHT).
- No `MODEL_ACK` message — delivery isn't currently acknowledged,
  only inferred by whether an update showed up before the round
  timeout.
- No model-update signing/authentication beyond libp2p's transport
  security (Noise) — a connected peer could in principle send a
  well-formed but bogus update.
- Tested at small scale (2–3 peers, a few hundred synthetic samples);
  not a production system.

## Troubleshooting

- **`ConnectionRefusedError` on connect**: make sure the bootstrap
  peer is already listening (its startup banner has printed) before
  starting the next one.
- **Round hangs**: check `--expected-peers` matches how many peers
  are actually going to send you an update this round; a stuck round
  will still resolve after `--round-timeout` seconds using whatever
  arrived.
- **Shape mismatch errors**: all peers in a run must use the same
  `--features` value.

## Roadmap (not yet implemented)

- 3+ peer automatic topologies via GossipSub
- Sample-weighted FedAvg is implemented; unweighted `simple_average`
  is available for comparison in `aggregation.py`
- Docker Compose for multi-peer demos
- Accuracy graphs across rounds
- Network failure / peer-dropout handling beyond round timeouts
