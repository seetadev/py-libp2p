import argparse

import trio_asyncio

from libp2p.peer.peer_node import run_peer
from libp2p.starknet_intents.bootsrap_node import run_bootstrap


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["bootstrap", "peer"])
    parser.add_argument(
        "--bootstrap-addr", help="Address of bootstrap peer for peer mode"
    )
    args = parser.parse_args()

    if args.mode == "bootstrap":
        trio_asyncio.run(run_bootstrap)
    elif args.mode == "peer":
        if not args.bootstrap_addr:
            print("Need --bootstrap-addr for peer mode")
            return
        trio_asyncio.run(lambda: run_peer(args.bootstrap_addr))


if __name__ == "__main__":
    main()
