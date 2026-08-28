# Demo runs

## 2-peer run

Terminal 1:

    python run_peer.py --port 8000 --peer-index 0 --n-peers 2

This prints a Peer ID and a listening multiaddr, e.g.:

    /ip4/127.0.0.1/tcp/8000/p2p/12D3KooW...

Terminal 2 (paste Peer A's multiaddr in):

    python run_peer.py --port 8001 --peer-index 1 --n-peers 2 \
        --peers /ip4/127.0.0.1/tcp/8000/p2p/12D3KooW...

Each peer trains locally, exchanges a `ModelUpdate` over
`/ml/federated-learning/1.0.0`, aggregates via FedAvg, and prints
local vs. federated accuracy for each round.

## 3-peer run

Terminal 1:

    python run_peer.py --port 8000 --peer-index 0 --n-peers 3

Terminal 2:

    python run_peer.py --port 8001 --peer-index 1 --n-peers 3 \
        --peers /ip4/127.0.0.1/tcp/8000/p2p/<PEER_A_ID>

Terminal 3 (bootstraps off both A and B so it waits for 2 updates/round):

    python run_peer.py --port 8002 --peer-index 2 --n-peers 3 \
        --peers /ip4/127.0.0.1/tcp/8000/p2p/<PEER_A_ID>,/ip4/127.0.0.1/tcp/8001/p2p/<PEER_B_ID>

Note that Peer A and Peer B, started before Peer C exists, won't have
Peer C in their own `--peers` list -- in this simplified prototype,
`--expected-peers` on A and B would need to be raised manually (or
set explicitly via `--expected-peers 2`) to wait for C's update too.
Automatic peer discovery (e.g. via GossipSub) would remove this
manual bootstrapping requirement; see README.md § Limitations.

## Expected output shape

    ==========================================
     P2P Federated Learning Peer
    ==========================================

    Peer ID:
    12D3KooW...

    Listening on:
    /ip4/127.0.0.1/tcp/8000/p2p/12D3KooW...

    Protocol:
    /ml/federated-learning/1.0.0

    Local dataset:
    360 samples, 10 features

    Expecting 1 peer(s) per round.

    Waiting for peers...

    ──────────────────────────────────────────
    ROUND 1
    ──────────────────────────────────────────

    Local accuracy:      78.42%
    Federated accuracy:  84.17%
