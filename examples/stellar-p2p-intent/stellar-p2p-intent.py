import trio
import json
import hashlib
import argparse
import random
import requests
import os
import secrets
import logging
from pathlib import Path
from typing import Optional, List
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__file__)


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
        self.received_intents = {}
        self.connected_peers = set()
        self.bootstrap_nodes = []

        # Create libp2p keypair from Stellar keypair
        if stellar_keypair:
            try:
                raw_secret = stellar_keypair.raw_secret_key()
                coincurve_priv = coincurve.PrivateKey(raw_secret)
                libp2p_priv = Secp256k1PrivateKey(coincurve_priv)
                self.libp2p_keypair = Libp2pKeyPair(
                    libp2p_priv, libp2p_priv.get_public_key()
                )
            except Exception as e:
                logger.warning(f"Failed to create libp2p keypair from Stellar key: {e}")
                self.libp2p_keypair = create_new_key_pair(secrets.token_bytes(32))
        else:
            self.libp2p_keypair = create_new_key_pair(secrets.token_bytes(32))

    async def start(self, bootstrap_addrs: Optional[list] = None):
        """Start the P2P node and Stellar services."""
        if self.listen_port <= 0:
            self.listen_port = random.randint(10000, 60000)
        logger.debug(f"Using port: {self.listen_port}")

        if not self.is_bootstrap and not bootstrap_addrs:
            server_addrs = load_bootstrap_addrs()
            if server_addrs:
                logger.info(f"Loaded {len(server_addrs)} bootstrap addresses from log")
                self.bootstrap_nodes.append(server_addrs[0])
            else:
                logger.warning("No bootstrap addresses found in log file")

        if bootstrap_addrs:
            for addr in bootstrap_addrs:
                if addr not in self.bootstrap_nodes:
                    self.bootstrap_nodes.append(addr)
        
        self.host = new_host(key_pair=self.libp2p_keypair)
        listen_addr = Multiaddr(f"/ip4/127.0.0.1/tcp/{self.listen_port}")

        async with self.host.run([listen_addr]), trio.open_nursery() as nursery:
            # Start peerstore cleanup task
            nursery.start_soon(self.host.get_peerstore().start_cleanup_task, 60)

            peer_id = self.host.get_id().pretty()
            addr_str = f"/ip4/127.0.0.1/tcp/{self.listen_port}/p2p/{peer_id}"
            await self._connect_bootstrap(self.bootstrap_nodes)
            self.dht = KadDHT(self.host, mode=DHTMode.SERVER if self.is_bootstrap else DHTMode.CLIENT)

            # Take all peer ids from host and add to dht
            for peer_id in self.host.get_peerstore().peer_ids():
                await self.dht.routing_table.add_peer(peer_id)
            logger.info(f"Connected to bootstrap nodes: {self.host.get_connected_peers()}")
            bootstrap_cmd = f"--bootstrap {addr_str}"
            logger.info("To connect to this node, use: %s", bootstrap_cmd)

            # Save server address in server mode
            if self.is_bootstrap:
                save_bootstrap_addr(addr_str)

            # Fund account if not bootstrap and has stellar keypair
            if not self.is_bootstrap and self.stellar_keypair:
                await self._ensure_funded()

            # Start DHT service
            async with background_trio_service(self.dht):
                gossip_router = GossipSub(
                    protocols=[self.PROTOCOL],
                    degree=6,
                    degree_low=4,
                    degree_high=12,
                    px_peers_count=6,
                )
                self.pubsub = Pubsub(self.host, gossip_router)

                # Subscribe to intent topic
                await self.pubsub.subscribe(self.PROTOCOL)
                self.pubsub.set_topic_validator(
                    self.PROTOCOL,
                    self._handle_message,
                    True,
                )
                logger.info("PubSub initialized and subscribed to protocol")

                # Start periodic status updates
                nursery.start_soon(self._status_monitor)

                # Keep running
                try:
                    await trio.sleep_forever()
                except (KeyboardInterrupt, trio.Cancelled):
                    logger.info("Shutting down...")
                    nursery.cancel_scope.cancel()

    async def _status_monitor(self):
        """Monitor connection status and log updates."""
        while True:
            try:
                current_peers = set(str(peer) for peer in self.host.get_connected_peers())
                
                # Log new connections
                new_peers = current_peers - self.connected_peers
                if new_peers:
                    logger.info(f"New peer connections: {list(new_peers)}")

                # Log disconnections
                lost_peers = self.connected_peers - current_peers
                if lost_peers:
                    logger.info(f"Lost peer connections: {list(lost_peers)}")
                self.connected_peers = current_peers

                # Periodic status
                if len(current_peers) > 0:
                    logger.debug(
                        f"Status - Connected: {len(current_peers)}, "
                        f"Pending intents: {len(self.pending_intents)}, "
                        f"Received intents: {len(self.received_intents)}"
                    )
                
                await trio.sleep(10)
            except Exception as e:
                logger.error(f"Status monitor error: {e}")
                await trio.sleep(5)

    async def _connect_bootstrap(self, bootstrap_addrs: list):
        """Connect to bootstrap nodes."""
        for addr in bootstrap_addrs:
            try:
                peerInfo = info_from_p2p_addr(Multiaddr(addr))
                self.host.get_peerstore().add_addrs(peerInfo.peer_id, peerInfo.addrs, 3600)
                await self.host.connect(peerInfo)
            except Exception as e:
                logger.error(f"Failed to connect to bootstrap node {addr}: {e}")

    async def _ensure_funded(self):
        """Ensure the Stellar account is funded."""
        try:
            await trio.to_thread.run_sync(
                self.server.load_account, self.stellar_keypair.public_key
            )
            logger.info("Stellar account already funded")
        except NotFoundError:
            logger.info("Funding account via Friendbot...")
            try:
                def fund_account():
                    response = requests.get(
                        f"{self.FRIENDBOT_URL}/?addr="
                        f"{self.stellar_keypair.public_key}",
                        timeout=30
                    )
                    response.raise_for_status()
                    return response.json()

                result = await trio.to_thread.run_sync(fund_account)
                logger.info("Account funded successfully")
                logger.debug(f"Friendbot response: {result}")
            except Exception as e:
                logger.error(f"Failed to fund account: {e}")
                raise

    async def _handle_message(self, peer_id: str, message):
        """Handle incoming P2P messages."""
        try:
            data = json.loads(message.data.decode("utf-8"))
            msg_type = data.get("type")

            logger.info(f"Received message type '{msg_type}' from {peer_id}")

            if msg_type == "intent":
                await self._handle_intent(peer_id, data)
            elif msg_type == "response":
                await self._handle_response(peer_id, data)
            elif msg_type == "status":
                await self._handle_status(peer_id, data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message from {peer_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling message from {peer_id}: {e}")

    async def _handle_intent(self, peer_id: str, intent_data: dict):
        """Handle received payment intents."""
        intent_id = intent_data.get("id", "unknown")
        
        logger.info(f"Processing intent {intent_id} from {peer_id}")
        logger.info(f"   Type: {intent_data.get('intent_type', 'unknown')}")
        logger.info(f"   From: {intent_data.get('from', 'unknown')[:8]}...")
        logger.info(f"   To: {intent_data.get('to', 'unknown')[:8]}...")
        logger.info(
            f"   Amount: {intent_data.get('amount')} "
            f"{intent_data.get('asset', 'XLM')}"
        )

        # Store received intent
        self.received_intents[intent_id] = {
            "data": intent_data,
            "peer_id": peer_id,
            "timestamp": trio.current_time()
        }

        # Validate intent
        if not self._validate_intent(intent_data):
            logger.warning(f"Intent {intent_id} validation failed")
            response = {
                "type": "response",
                "intent_id": intent_id,
                "from": self.stellar_keypair.public_key,
                "accepted": False,
                "reason": "validation_failed",
                "timestamp": trio.current_time(),
            }
            await self._publish_message(response)
            return

        # Check if intent is for us
        if intent_data.get("to") == self.stellar_keypair.public_key:
            logger.info(f"Intent {intent_id} is addressed to this node - auto-accepting")
            response = {
                "type": "response",
                "intent_id": intent_id,
                "from": self.stellar_keypair.public_key,
                "accepted": True,
                "timestamp": trio.current_time(),
            }
            await self._publish_message(response)
        else:
            logger.info(f"Intent {intent_id} not for this node - ignoring")

    async def _handle_response(self, peer_id: str, response_data: dict):
        """Handle responses to our intents."""
        intent_id = response_data.get("intent_id")
        accepted = response_data.get("accepted", False)
        reason = response_data.get("reason", "")

        logger.info(f"Received response for intent {intent_id} from {peer_id}")
        logger.info(f"   Status: {'ACCEPTED' if accepted else 'REJECTED'}")
        if reason:
            logger.info(f"   Reason: {reason}")

        if accepted and intent_id in self.pending_intents:
            logger.info("Submitting transaction to Stellar network...")
            try:
                transaction = self.pending_intents[intent_id]["transaction"]

                def submit_tx():
                    response = self.server.submit_transaction(transaction)
                    return response

                result = await trio.to_thread.run_sync(submit_tx)
                tx_hash = result.get("hash", result.get("id", "unknown"))
                
                logger.info("Transaction submitted successfully!")
                logger.info(f"   Hash: {tx_hash}")
                logger.info(
                    f"   Explorer: "
                    f"https://stellar.expert/explorer/testnet/tx/{tx_hash}"
                )

                # Clean up
                del self.pending_intents[intent_id]
                
            except Exception as e:
                logger.error(f"Failed to submit transaction: {e}")
        elif not accepted:
            logger.warning(f"Intent {intent_id} was rejected by peer")
            # Clean up rejected intent
            if intent_id in self.pending_intents:
                del self.pending_intents[intent_id]

    async def _handle_status(self, peer_id: str, status_data: dict):
        """Handle status messages from peers."""
        logger.debug(f"Status from {peer_id}: {status_data}")

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
        missing_fields = [field for field in required_fields if field not in intent_data]
        if missing_fields:
            logger.error(f"Missing required fields in intent: {missing_fields}")
            return False

        # Check timestamp (not too old or in future)
        current_time = trio.current_time()
        intent_time = intent_data["timestamp"]
        time_diff = abs(current_time - intent_time)
        
        if time_diff > 600:  # 10 minutes
            logger.error(f"Intent timestamp is too old/future: {time_diff}s")
            return False

        # Validate amount
        try:
            amount = float(intent_data["amount"])
            if amount <= 0:
                logger.error("Intent amount must be positive")
                return False
        except (ValueError, TypeError):
            logger.error("Invalid amount format")
            return False

        # Validate XDR
        try:
            from stellar_sdk import TransactionEnvelope
            envelope = TransactionEnvelope.from_xdr(
                intent_data["transaction_xdr"],
                Network.TESTNET_NETWORK_PASSPHRASE
            )
            
            # Additional validation: check if transaction is properly signed
            if not envelope.transaction.signatures:
                logger.error("Transaction is not signed")
                return False
                
        except Exception as e:
            logger.error(f"Invalid transaction XDR: {e}")
            return False

        return True

    async def send_payment_intent(
        self, destination: str, amount: str, asset_code: str = "XLM"
    ):
        """Create and send a payment intent."""
        try:
            logger.info(
                f"Creating payment intent: {amount} {asset_code}"
                f" to {destination[:8]}..."
            )

            # Verify we have connected peers
            if len(self.host.get_connected_peers()) == 0:
                logger.error("No connected peers to send intent to!")
                return False

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
                        base_fee=100,  # Explicit base fee
                    )
                    .append_payment_op(destination, asset, amount)
                    .set_timeout(300)  # 5 minute timeout
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
            self.pending_intents[intent_id] = {
                "transaction": transaction,
                "intent_data": intent,
                "created_at": trio.current_time()
            }

            # Publish intent
            await self._publish_message(intent)
            logger.info(f"Payment intent published: {intent_id}")
            logger.info(f"Waiting for response from peers...")
            
            return True

        except Exception as e:
            logger.error(f"Failed to create payment intent: {e}")
            return False

    async def send_status_update(self):
        """Send status update to network."""
        status = {
            "type": "status",
            "peer_id": str(self.host.get_id()),
            "stellar_address": self.stellar_keypair.public_key,
            "connected_peers": len(self.host.get_connected_peers()),
            "pending_intents": len(self.pending_intents),
            "timestamp": trio.current_time(),
        }
        await self._publish_message(status)

    async def _publish_message(self, message: dict):
        """Publish a message to the P2P network."""
        try:
            if not self.pubsub:
                logger.error("PubSub not initialized - cannot publish message")
                return False
                
            message_bytes = json.dumps(message, sort_keys=True).encode("utf-8")
            await self.pubsub.publish(self.PROTOCOL, message_bytes)
            logger.debug(f"Published message type: {message.get('type')}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False


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
        action="append",
        help="Bootstrap node address (can be used multiple times)",
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
    
    # Debug options
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

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
        print(f"1. Bootstrap: python {__file__} --bootstrap --port 4001")
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
    stellar_keypair = None
    if args.secret:
        try:
            stellar_keypair = Keypair.from_secret(args.secret)
        except Exception as e:
            logger.error(f"Invalid Stellar secret key: {e}")
            return

    node = StellarP2PIntents(
        stellar_keypair=stellar_keypair,
        listen_port=args.port,
        is_bootstrap=args.bootstrap,
    )

    try:
        if args.bootstrap:
            # Bootstrap node
            logger.info("Starting bootstrap node...")
            await node.start()
            
        elif args.send_to:
            # Sender node
            bootstrap_addrs = load_bootstrap_addrs()
            if not bootstrap_addrs:
                logger.error("No bootstrap addresses found for sender node!")
                logger.error("Please ensure:")
                logger.error("1. Bootstrap node is running")
                logger.error("2. Use --bootstrap-addr or set environment variables")
                return

            logger.info(f"Using bootstrap addresses: {bootstrap_addrs}")

            # Start node and send payment
            async with trio.open_nursery() as nursery:
                nursery.start_soon(node.start, bootstrap_addrs)
                await trio.sleep(8)  # Let node initialize and connect properly

                # Verify connection before sending
                if len(node.host.get_connected_peers()) == 0:
                    logger.error("Failed to connect to any peers!")
                    nursery.cancel_scope.cancel()
                    return

                # Send payment
                success = await node.send_payment_intent(
                    args.send_to,
                    args.amount,
                    args.asset,
                )
                
                if success:
                    logger.info("Waiting for response...")
                    await trio.sleep(30)  # Wait for response
                else:
                    logger.error("Failed to send payment intent")
                    
                nursery.cancel_scope.cancel()

        elif args.listen:
            # Receiver node
            bootstrap_addrs = load_bootstrap_addrs()
            if not bootstrap_addrs:
                logger.error("No bootstrap addresses found for receiver node!")
                logger.error("Please ensure:")
                logger.error("1. Bootstrap node is running")
                logger.error("2. Use --bootstrap-addr or set environment variables")
                return

            logger.info(f"Using bootstrap addresses: {bootstrap_addrs}")
            await node.start(bootstrap_addrs)
            
        else:
            print("Must specify --bootstrap, --listen, --send-to, or --demo")

    except KeyboardInterrupt:
        logger.info("Goodbye!")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)


def load_bootstrap_addrs() -> List[str]:
    """Load bootstrap addresses from the log file."""
    bootstrap_log = Path("stellar_bootstrap_addrs.txt")
    if bootstrap_log.exists():
        try:
            with open(bootstrap_log) as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.warning(f"Failed to load bootstrap addresses: {e}")
    return []


def save_bootstrap_addr(addr: str):
    """Save bootstrap node address to file for other nodes to discover."""
    bootstrap_log = Path("stellar_bootstrap_addrs.txt")
    try:
        with open(bootstrap_log, "w") as f:
            f.write(addr + "\n")
        logger.info(f"Saved bootstrap address to log file: {addr}")
    except Exception as e:
        logger.error(f"Failed to save bootstrap address: {e}")


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
