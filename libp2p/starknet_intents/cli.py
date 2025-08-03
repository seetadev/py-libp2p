import argparse
import json
import os

import trio_asyncio

from libp2p.starknet_intents.bootsrap_node import run_bootstrap
from libp2p.starknet_intents.intents import create_intent
from libp2p.starknet_intents.peer_node import run_peer, send_intent_via_peer


def cli_main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    # Bootstrap node
    subparsers.add_parser("bootstrap", help="Run bootstrap libp2p node")

    # Peer node
    peer_parser = subparsers.add_parser("peer", help="Run intent-aware peer")
    peer_parser.add_argument("--bootstrap-addr", required=True)

    # Generate intent
    gen_parser = subparsers.add_parser(
        "generate-intent", help="Create and save an intent"
    )
    gen_parser.add_argument("--sender", required=True)
    gen_parser.add_argument("--contract", required=True)
    gen_parser.add_argument("--calldata", nargs="+", type=int, required=True)
    gen_parser.add_argument("--nonce", type=int, required=True)
    gen_parser.add_argument("--output", default="intent.json")

    # Send intent
    send_parser = subparsers.add_parser(
        "send-intent", help="Broadcast intent from file"
    )
    send_parser.add_argument("--bootstrap-addr", required=True)
    send_parser.add_argument("--file", default="intent.json")

    args = parser.parse_args()

    if args.command == "bootstrap":
        trio_asyncio.run(run_bootstrap)

    elif args.command == "peer":
        trio_asyncio.run(lambda: run_peer(args.bootstrap_addr))

    elif args.command == "generate-intent":
        intent = create_intent(
            sender=args.sender,
            contract_address=args.contract,
            calldata=args.calldata,
            nonce=args.nonce,
        )
        with open(args.output, "w") as f:
            json.dump(intent, f, indent=2)
        print(f"[+] Intent saved to {args.output}")

    elif args.command == "send-intent":
        if not os.path.exists(args.file):
            print(f"[!] Intent file {args.file} does not exist.")
            return

        with open(args.file) as f:
            intent = json.load(f)

        trio_asyncio.run(lambda: send_intent_via_peer(args.bootstrap_addr, intent))

    else:
        parser.print_help()


if __name__ == "__main__":
    cli_main()
