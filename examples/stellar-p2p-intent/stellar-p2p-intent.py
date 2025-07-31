#!/usr/bin/env python3
"""
Stellar P2P Intents Example

A reference implementation showing how to use py-libp2p for decentralized
coordination of Stellar transactions. Agents can exchange signed Stellar
transaction intents peer-to-peer before submitting to the network.

Usage:
    # Terminal 1 - Start bootstrap node
    python stellar_p2p_intents.py --bootstrap

    # Terminal 2 - Start receiver (Bob)
    python stellar_p2p_intents.py --secret SXXXXXXX --listen --port 4002

    # Terminal 3 - Send payment intent (Alice)
    python stellar_p2p_intents.py --secret SXXXXXXX --send-to GXXXXXXX \
        --amount 10 --port 4003

Requirements:
    pip install trio stellar-sdk py-libp2p coincurve requests
"""

import trio
import json
import hashlib
import argparse
import requests
import os
from pathlib import Path
from typing import Optional
from multiaddr import Multiaddr

# Stellar SDK imports
from stellar_sdk import Asset, Server, Keypair, TransactionBuilder, Network
from stellar_sdk.exceptions import NotFoundError

# libp2p imports
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair, Secp256k1PrivateKey
from libp2p.crypto.keys import KeyPair as Libp2pKeyPair
from libp2p.pubsub.pubsub import Pubsub
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.kad_dht.kad_dht import KadDHT, DHTMode
from libp2p.tools.utils import info_from_p2p_addr
from libp2p.tools.async_service import background_trio_service
import coincurve


class StellarP2PIntents:
    """A P2P node for exchanging Stellar transaction intents."""

    PROTOCOL = "/stellar/intent/1.0.0"
    HORIZON_URL = "https://horizon-testnet.stellar.org"
    FRIENDBOT_URL = "https://friendbot.stellar.org"

    def __init__(
        self,
        stellar_keypair: Optional[Keypair] = None,
        listen_port: int = 4001,
        is_bootstrap: bool = False,
    ):
        self.stellar_keypair = stellar_keypair or Keypair.random()
        self.is_bootstrap = is_bootstrap
        self.listen_port = listen_port
        self.server = Server(self.HORIZON_URL)

        # P2P components
        self.host = None
        self.dht = None
        self.pubsub = None
        self.pending_intents = {}
        self.nursery = None

        # Create libp2p keypair from Stellar keypair
        if stellar_keypair:
            raw_secret = stellar_keypair.raw_secret_key()
            coincurve_priv = coincurve.PrivateKey(raw_secret)
            libp2p_priv = Secp256k1PrivateKey(coincurve_priv)
            self.libp2p_keypair = Libp2pKeyPair(
                libp2p_priv, libp2p_priv.get_public_key()
            )
        else:
            self.libp2p_keypair = create_new_key_pair()

    async def start(self, bootstrap_addrs: Optional[list] = None):
        """Start the P2P node and Stellar services."""
        listen_addr = f"/ip4/0.0.0.0/tcp/{self.listen_port}"
        listen_multiaddr = Multiaddr(listen_addr)

        # Create host WITHOUT bootstrap addresses
        self.host = new_host(self.libp2p_keypair)

        print(
            f"{'Bootstrap' if self.is_bootstrap else 'Regular'} node "
            "starting..."
        )
        print(f"Stellar Address: {self.stellar_keypair.public_key}")
        print(f"P2P Node ID: {self.host.get_id()}")
        print(f"Listening on: {listen_addr}")

        # Start services in nursery
        async with trio.open_nursery() as nursery:
            self.nursery = nursery
            # Start peerstore cleanup task
            nursery.start_soon(self.host.get_peerstore().start_cleanup_task, 60)
            
            async with self.host.run([listen_multiaddr]):
                await trio.sleep(0.1)  # Let host initialize

                # Connect to bootstrap nodes FIRST (before DHT)
                if not self.is_bootstrap and bootstrap_addrs:
                    await self._connect_bootstrap(bootstrap_addrs)

                # Initialize DHT AFTER bootstrap connections
                dht_mode = DHTMode.SERVER if self.is_bootstrap else DHTMode.CLIENT
                self.dht = KadDHT(self.host, mode=dht_mode)

                # Add all connected peers to DHT routing table
                for peer_id in self.host.get_peerstore().peer_ids():
                    await self.dht.routing_table.add_peer(peer_id)

                print(f"Connected peers after bootstrap: {len(self.host.get_connected_peers())}")

                # Start DHT using background service
                async with background_trio_service(self.dht):
                    await trio.sleep(0.1)  # Let DHT initialize

                    # Initialize PubSub AFTER DHT is running
                    gossip_router = GossipSub(
                        [self.PROTOCOL],
                        10,
                        9,
                        11,
                        px_peers_count=30,
                    )
                    self.pubsub = Pubsub(self.host, gossip_router)

                    # Subscribe to intent topic
                    await self.pubsub.subscribe(self.PROTOCOL)
                    self.pubsub.set_topic_validator(
                        self.PROTOCOL,
                        self._handle_message,
                        True,
                    )

                    # Fund account if not bootstrap
                    if not self.is_bootstrap:
                        await self._ensure_funded()

                    # If this is a bootstrap node, save address for others to use
                    if self.is_bootstrap:
                        peer_id = self.host.get_id().pretty()
                        full_addr = f"/ip4/127.0.0.1/tcp/{self.listen_port}/p2p/{peer_id}"
                        save_bootstrap_addr(full_addr)
                        print(f"Bootstrap node address: {full_addr}")

                    print("P2P node ready!")
                    print(f"Connected peers: {len(self.host.get_connected_peers())}")

                    # Keep running
                    try:
                        await trio.sleep_forever()
                    except (KeyboardInterrupt, trio.Cancelled):
                        print("\nShutting down...")
                        nursery.cancel_scope.cancel()

    async def _connect_bootstrap(self, bootstrap_addrs: list):
        """Connect to bootstrap nodes."""
        for addr_str in bootstrap_addrs:
            try:
                peer_info = info_from_p2p_addr(Multiaddr(addr_str))
                # Add peer to peerstore first
                self.host.get_peerstore().add_addrs(
                    peer_info.peer_id, peer_info.addrs, 3600
                )
                await self.host.connect(peer_info)
                print(f"Connected to bootstrap: {addr_str}")
            except Exception as e:
                print(f"Failed to connect to {addr_str}: {e}")

    async def _ensure_funded(self):
        """Ensure the Stellar account is funded."""
        try:
            await trio.to_thread.run_sync(
                self.server.load_account, self.stellar_keypair.public_key
            )
            print("Stellar account already funded")
        except NotFoundError:
            print("Funding account via Friendbot...")
            try:

                def fund_account():
                    response = requests.get(
                        f"{self.FRIENDBOT_URL}/?addr="
                        f"{self.stellar_keypair.public_key}"
                    )
                    response.raise_for_status()
                    return response.json()

                await trio.to_thread.run_sync(fund_account)
                print("Account funded successfully")
            except Exception as e:
                print(f"Failed to fund account: {e}")

    async def _handle_message(self, peer_id: str, message):
        """Handle incoming P2P messages."""
        try:
            data = json.loads(message.data.decode("utf-8"))
            msg_type = data.get("type")

            if msg_type == "intent":
                await self._handle_intent(peer_id, data)
            elif msg_type == "response":
                await self._handle_response(peer_id, data)
            else:
                print(f"Unknown message type: {msg_type}")
        except Exception as e:
            print(f"Error handling message: {e}")

    async def _handle_intent(self, peer_id: str, intent_data: dict):
        """Handle received payment intents."""
        print(f"\nReceived intent from {peer_id}")
        print(f"   Type: {intent_data.get('intent_type', 'unknown')}")
        print(f"   From: {intent_data.get('from', 'unknown')[:8]}...")
        print(f"   To: {intent_data.get('to', 'unknown')[:8]}...")
        print(
            f"   Amount: {intent_data.get('amount')} "
            f"{intent_data.get('asset', 'XLM')}"
        )

        # Validate intent
        if not self._validate_intent(intent_data):
            print("Intent validation failed")
            return

        # Check if intent is for us
        if intent_data.get("to") == self.stellar_keypair.public_key:
            print("Intent addressed to this node - auto-accepting")
            response = {
                "type": "response",
                "intent_id": intent_data["id"],
                "from": self.stellar_keypair.public_key,
                "accepted": True,
                "timestamp": trio.current_time(),
            }
            await self._publish_message(response)
        else:
            print("Intent not for this node - ignoring")

    async def _handle_response(self, peer_id: str, response_data: dict):
        """Handle responses to our intents."""
        intent_id = response_data.get("intent_id")
        accepted = response_data.get("accepted", False)

        print(f"\nReceived response from {peer_id}")
        print(f"   Intent ID: {intent_id}")
        print(f"   Status: {'ACCEPTED' if accepted else 'REJECTED'}")

        if accepted and intent_id in self.pending_intents:
            print("Submitting transaction to Stellar network...")
            try:
                transaction = self.pending_intents[intent_id]

                def submit_tx():
                    response = self.server.submit_transaction(transaction)
                    return response["hash"]

                tx_hash = await trio.to_thread.run_sync(submit_tx)
                print("Transaction submitted successfully!")
                print(f"   Hash: {tx_hash}")
                print(
                    f"   Explorer: "
                    f"https://stellar.expert/explorer/testnet/tx/{tx_hash}"
                )

                # Clean up
                del self.pending_intents[intent_id]
            except Exception as e:
                print(f"Failed to submit transaction: {e}")

    def _validate_intent(self, intent_data: dict) -> bool:
        """Validate a received intent."""
        required_fields = [
            "id",
            "intent_type",
            "from",
            "to",
            "amount",
            "transaction_xdr",
            "timestamp",
        ]

        # Check required fields
        if not all(field in intent_data for field in required_fields):
            print("Missing required fields in intent")
            return False

        # Check timestamp (not too old)
        current_time = trio.current_time()
        if abs(current_time - intent_data["timestamp"]) > 300:  # 5 minutes
            print("Intent timestamp is too old")
            return False

        # Validate XDR
        try:
            from stellar_sdk import TransactionEnvelope

            TransactionEnvelope.from_xdr(
                intent_data["transaction_xdr"],
                Network.TESTNET_NETWORK_PASSPHRASE
            )
        except Exception:
            print("Invalid transaction XDR")
            return False

        return True

    async def send_payment_intent(
        self, destination: str, amount: str, asset_code: str = "XLM"
    ):
        """Create and send a payment intent."""
        try:
            print(
                f"\nCreating payment intent: {amount} {asset_code}"
                f" to {destination[:8]}..."
            )

            # Create transaction
            def create_tx():
                source_account = self.server.load_account(
                    self.stellar_keypair.public_key
                )
                asset = (
                    Asset.native()
                    if asset_code == "XLM"
                    else Asset(asset_code, destination)
                )

                transaction = (
                    TransactionBuilder(
                        source_account=source_account,
                        network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                    )
                    .append_payment_op(destination, asset, amount)
                    .set_timeout(30)
                    .build()
                )
                transaction.sign(self.stellar_keypair)
                return transaction

            transaction = await trio.to_thread.run_sync(create_tx)

            # Create intent
            intent_data = {
                "from": self.stellar_keypair.public_key,
                "to": destination,
                "amount": amount,
                "asset": asset_code,
            }

            intent_id = (
                "intent_" + hashlib.sha256(
                    json.dumps(intent_data, sort_keys=True).encode()
                ).hexdigest()[:16]
            )

            intent = {
                "type": "intent",
                "id": intent_id,
                "intent_type": "payment",
                "from": self.stellar_keypair.public_key,
                "to": destination,
                "amount": amount,
                "asset": asset_code,
                "transaction_xdr": transaction.to_xdr(),
                "timestamp": trio.current_time(),
            }

            # Store pending intent
            self.pending_intents[intent_id] = transaction

            # Publish intent
            await self._publish_message(intent)
            print(f"Payment intent published: {intent_id}")

        except Exception as e:
            print(f"Failed to create payment intent: {e}")

    async def _publish_message(self, message: dict):
        """Publish a message to the P2P network."""
        try:
            message_bytes = json.dumps(message).encode("utf-8")
            await self.pubsub.publish(self.PROTOCOL, message_bytes)
        except Exception as e:
            print(f"Failed to publish message: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Stellar P2P Intents Example")

    # Node configuration
    parser.add_argument(
        "--bootstrap", action="store_true", help="Run as bootstrap node"
    )
    parser.add_argument("--secret", help="Stellar secret key")
    parser.add_argument("--port", type=int, default=4001, help="Listen port")
    parser.add_argument(
        "--bootstrap-addr",
        default="/ip4/127.0.0.1/tcp/4001",
        help="Bootstrap node address",
    )

    # Actions
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Listen for intents",
    )
    parser.add_argument("--send-to", help="Send payment to this address")
    parser.add_argument("--amount", default="10", help="Payment amount")
    parser.add_argument("--asset", default="XLM", help="Asset code")

    # Demo mode
    parser.add_argument(
        "--demo", action="store_true", help="Run demo (create test accounts)"
    )

    args = parser.parse_args()

    # Demo mode - create test accounts
    if args.demo:
        print("DEMO MODE: Creating test accounts...")
        alice = Keypair.random()
        bob = Keypair.random()

        print("\nAlice (Sender):")
        print(f"   Public:  {alice.public_key}")
        print(f"   Secret:  {alice.secret}")

        print("\nBob (Receiver):")
        print(f"   Public:  {bob.public_key}")
        print(f"   Secret:  {bob.secret}")

        print("\nDemo Commands:")
        print(f"1. Bootstrap: python {__file__} --bootstrap")
        print(
            f"2. Bob:       python {__file__} --secret {bob.secret} "
            "--listen --port 4002"
        )
        print(
            f"3. Alice:     python {__file__} --secret {alice.secret} "
            f"--send-to {bob.public_key} --amount 10 --port 4003"
        )
        return

    # Create node
    stellar_keypair = Keypair.from_secret(args.secret) if args.secret else None
    node = StellarP2PIntents(
        stellar_keypair=stellar_keypair,
        listen_port=args.port,
        is_bootstrap=args.bootstrap,
    )

    try:
        if args.bootstrap:
            # Bootstrap node
            await node.start()
        elif args.send_to:
            # Sender node
            bootstrap_addrs = get_bootstrap_addresses()
            valid_bootstrap_addrs = []

            for addr in bootstrap_addrs:
                if validate_bootstrap_addr(addr):
                    valid_bootstrap_addrs.append(addr)
                else:
                    print(f"Skipping invalid bootstrap address: {addr}")

            if not valid_bootstrap_addrs:
                print("No valid bootstrap addresses found. Please ensure:")
                print("1. Bootstrap node is running")
                print("2. Bootstrap addresses include peer IDs")
                print("3. Use format: /ip4/127.0.0.1/tcp/4001/p2p/<peer_id>")
                return

            # Start node in background and send payment
            async with trio.open_nursery() as nursery:
                nursery.start_soon(node.start, valid_bootstrap_addrs)
                await trio.sleep(3)  # Let node initialize and connect

                # Send payment
                await node.send_payment_intent(
                    args.send_to,
                    args.amount,
                    args.asset,
                )
                await trio.sleep(10)  # Wait for response
                nursery.cancel_scope.cancel()

        elif args.listen:
            # Receiver node
            bootstrap_addrs = get_bootstrap_addresses()
            valid_bootstrap_addrs = []

            for addr in bootstrap_addrs:
                if validate_bootstrap_addr(addr):
                    valid_bootstrap_addrs.append(addr)
                else:
                    print(f"Skipping invalid bootstrap address: {addr}")

            if not valid_bootstrap_addrs:
                print("No valid bootstrap addresses found. Please ensure:")
                print("1. Bootstrap node is running")
                print("2. Bootstrap addresses include peer IDs")
                print("3. Use format: /ip4/127.0.0.1/tcp/4001/p2p/<peer_id>")
                return

            await node.start(valid_bootstrap_addrs)
        else:
            print("Must specify --bootstrap, --listen, --send-to, or --demo")

    except KeyboardInterrupt:
        print("\nGoodbye!")


def get_bootstrap_addresses():
    """Get bootstrap node addresses from various sources."""
    # 1. Environment variables (highest priority)
    env_addrs = os.getenv("STELLAR_BOOTSTRAP_ADDRS")
    if env_addrs:
        return [addr.strip() for addr in env_addrs.split(",")]

    # 2. Single environment variable
    single_addr = os.getenv("STELLAR_BOOTSTRAP_ADDR")
    if single_addr:
        return [single_addr]

    # 3. Configuration file
    config_file = Path("stellar_bootstrap.json")
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
                if "bootstrap_nodes" in config:
                    return config["bootstrap_nodes"]
        except Exception as e:
            print(f"Failed to load config file: {e}")

    # 4. Load from local bootstrap log file
    bootstrap_log = Path("stellar_bootstrap_addrs.txt")
    if bootstrap_log.exists():
        try:
            with open(bootstrap_log) as f:
                addrs = [line.strip() for line in f if line.strip()]
                if addrs:
                    return addrs
        except Exception as e:
            print(f"Failed to load bootstrap log: {e}")

    # 5. Well-known production addresses (if any)
    production_bootstraps = [
        # These would be real addresses of hosted bootstrap nodes
        # "/dns4/bootstrap1.stellar-intents.org/tcp/4001/p2p/12D3Koo...",
        # "/dns4/bootstrap2.stellar-intents.org/tcp/4001/p2p/12D3Koo...",
    ]

    if production_bootstraps:
        return production_bootstraps

    # 6. Fallback to localhost for development
    return ["/ip4/127.0.0.1/tcp/4001"]


def save_bootstrap_addr(addr: str):
    """Save bootstrap node address to file for other nodes to discover."""
    bootstrap_log = Path("stellar_bootstrap_addrs.txt")
    try:
        with open(bootstrap_log, "w") as f:
            f.write(addr + "\n")
        print(f"Saved bootstrap address: {addr}")
    except Exception as e:
        print(f"Failed to save bootstrap address: {e}")


def validate_bootstrap_addr(addr_str: str) -> bool:
    """Validate that a bootstrap address has the required peer ID."""
    try:
        addr = Multiaddr(addr_str)
        # Check if address contains peer ID
        protocols = [proto.code for proto in addr.protocols()]
        return 421 in protocols  # 421 is the protocol code for /p2p/
    except Exception:
        return False


if __name__ == "__main__":
    trio.run(main)
