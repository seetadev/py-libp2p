import json
import logging
import subprocess

from multiaddr import Multiaddr
import trio
import trio_asyncio

from libp2p import new_host
from libp2p.starknet_intents.discovery import bootstrap_to_peer
from libp2p.starknet_intents.pubsub_intents import IntentPubSub

logging.basicConfig(level=logging.INFO)
TOPIC = "/starknet/intent/1.0.0"


def run_fusion_order(from_token: str, to_token: str, amount: str) -> str:
    """
    Call a Node.js script to create and submit a Fusion+ order.
    Replace with REST call or subprocess as needed.
    """
    try:
        result = subprocess.check_output(
            ["node", "fusion_order.js", from_token, to_token, amount]
        )
        return result.decode().strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.output.decode().strip()}"


async def run_resolver_peer(bootstrap_addr: str) -> None:
    host = new_host()

    async with host.run(listen_addrs=[Multiaddr("/ip4/0.0.0.0/tcp/0")]):
        logging.info("[RESOLVER PEER] ID: %s", host.get_id())
        await bootstrap_to_peer(host, bootstrap_addr)

        pub = IntentPubSub(host, host.get_peerstore())

        async def handle_intent(intent_str: str) -> None:
            try:
                intent = json.loads(intent_str)
                meta = intent["intent_metadata"]
                logging.info("Received Intent:\n%s", json.dumps(intent, indent=2))

                from_token = meta["token_from"]
                to_token = meta["token_to"]
                amount = str(intent["calldata"][-1])

                logging.info(
                    "Submitting Fusion order: %s → %s (%s)",
                    from_token,
                    to_token,
                    amount,
                )
                result = run_fusion_order(from_token, to_token, amount)
                logging.info("Fusion Result: %s", result)
            except Exception as e:
                logging.error("Failed to handle intent: %s", e)

        async with trio.open_nursery() as nursery:
            nursery.start_soon(pub.subscribe_and_handle, TOPIC, handle_intent)
            await trio.sleep_forever()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: resolver_peer.py <bootstrap-multiaddr>")
        exit(1)
    trio_asyncio.run(lambda: run_resolver_peer(sys.argv[1]))
