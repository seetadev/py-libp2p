"""
run_peer.py
-----------
CLI entry point.

Two-peer example:
    python run_peer.py --port 8000 --peer-index 0 --n-peers 2
    python run_peer.py --port 8001 --peer-index 1 --n-peers 2 \\
        --peers /ip4/127.0.0.1/tcp/8000/p2p/<PEER_A_ID>

Three-peer example (peer C bootstraps off both A and B):
    python run_peer.py --port 8000 --peer-index 0 --n-peers 3
    python run_peer.py --port 8001 --peer-index 1 --n-peers 3 \\
        --peers /ip4/127.0.0.1/tcp/8000/p2p/<PEER_A_ID>
    python run_peer.py --port 8002 --peer-index 2 --n-peers 3 \\
        --peers /ip4/127.0.0.1/tcp/8000/p2p/<PEER_A_ID>,/ip4/127.0.0.1/tcp/8001/p2p/<PEER_B_ID>

Note: --peers takes a comma-separated list of multiaddrs, and
--n-peers tells every process how many *total* peers exist in this
run (used only for slicing the shared synthetic dataset into non-IID
shards -- it is not itself transmitted over the network).
"""

import argparse
import logging

import trio

from federated_learning.dataset import load_local_dataset
from federated_learning.peer import FederatedPeer


def parse_args():
    parser = argparse.ArgumentParser(description="P2P Federated Learning Peer")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peers", type=str, default="",
                         help="Comma-separated multiaddrs of peers to connect to on startup")
    parser.add_argument("--peer-index", type=int, default=0,
                         help="Which non-IID data shard this peer uses")
    parser.add_argument("--n-peers", type=int, default=2,
                         help="Total peers in this run (for dataset sharding, not networking)")
    parser.add_argument("--expected-peers", type=int, default=None,
                         help="How many OTHER peers to wait for updates from each round "
                              "(defaults to the number of --peers connected to)")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--samples", type=int, default=900)
    parser.add_argument("--features", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--round-timeout", type=float, default=60.0,
                         help="Seconds to wait for peer updates before aggregating with what arrived")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


async def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    peer_addrs = [a.strip() for a in args.peers.split(",") if a.strip()]
    expected_peers = args.expected_peers if args.expected_peers is not None else len(peer_addrs)

    X_train, X_test, y_train, y_test = load_local_dataset(
        peer_index=args.peer_index,
        n_peers=args.n_peers,
        n_samples=args.samples,
        n_features=args.features,
        seed=args.seed,
    )

    peer = FederatedPeer(
        port=args.port,
        n_features=args.features,
        expected_peers=expected_peers,
        rounds=args.rounds,
        seed=args.seed,
        round_timeout=args.round_timeout,
    )

    await peer.run(peer_addrs, X_train, y_train, X_test, y_test)


if __name__ == "__main__":
    trio.run(main)
