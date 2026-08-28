"""
peer.py
-------
FederatedPeer: the main abstraction tying together libp2p networking,
local ML training, and decentralized FedAvg.

Each peer independently aggregates whatever updates it has collected
for a round -- nobody acts as a central coordinator. As long as every
peer eventually sees the same set of updates for round N, they all
converge on the same global model.

Supports an arbitrary number of peers (not just 2): pass a list of
bootstrap multiaddrs and `expected_peers = len(peer_addrs)`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import trio
import multiaddr
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.network.stream.net_stream_interface import INetStream

from . import model as model_lib
from . import training
from .aggregation import fed_avg
from .protocol import PROTOCOL_ID, ValidationError, receive_model_update, send_model_update, validate_update
from .serialization import ModelUpdate, SerializationError

logger = logging.getLogger("federated_peer")


@dataclass
class RoundState:
    """Tracks received updates, keyed by round then by sender peer_id.

    Keying by peer_id means a duplicate/retransmitted update from the
    same peer in the same round simply overwrites the prior entry
    instead of being double-counted in aggregation.
    """
    received: dict = field(default_factory=dict)  # {round: {peer_id: ModelUpdate}}

    def store(self, update: ModelUpdate) -> None:
        self.received.setdefault(update.round, {})[update.peer_id] = update

    def count_for_round(self, round_number: int) -> int:
        return len(self.received.get(round_number, {}))

    def updates_for_round(self, round_number: int) -> list[ModelUpdate]:
        return list(self.received.get(round_number, {}).values())


class FederatedPeer:
    def __init__(self, port: int, n_features: int, expected_peers: int, rounds: int = 3,
                 seed: int | None = None, round_timeout: float = 60.0):
        self.port = port
        self.n_features = n_features
        self.expected_peers = expected_peers  # OTHER peers, not counting self
        self.rounds = rounds
        self.seed = seed
        self.round_timeout = round_timeout

        self.model = model_lib.new_model(seed=seed)
        self.round_state = RoundState()
        self.peer_id: str | None = None
        self.host = None

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------

    async def run(self, bootstrap_addrs: list[str], X_train, y_train, X_test, y_test):
        """
        Single entry point: brings the libp2p host up, connects to any
        bootstrap peers, then drives all training rounds -- all inside
        the host's lifetime so streams stay valid throughout.
        """
        key_pair = create_new_key_pair()
        self.host = new_host(key_pair=key_pair)
        self.peer_id = str(self.host.get_id())

        listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{self.port}")

        async with self.host.run(listen_addrs=[listen_addr]):
            self.host.set_stream_handler(PROTOCOL_ID, self._stream_handler)
            self._print_startup_banner(X_train)

            for addr in bootstrap_addrs:
                await self.connect_to_peer(addr)

            await self._run_all_rounds(X_train, y_train, X_test, y_test, bootstrap_addrs)

    def _print_startup_banner(self, X_train):
        addrs = self.host.get_addrs()
        print("=" * 42)
        print(" P2P Federated Learning Peer")
        print("=" * 42)
        print(f"\nPeer ID:\n{self.peer_id}\n")
        print("Listening on:")
        for a in addrs:
            print(f"{a}")
        print(f"\nProtocol:\n{PROTOCOL_ID}")
        print(f"\nLocal dataset:\n{len(X_train)} samples, {self.n_features} features")
        print(f"\nExpecting {self.expected_peers} peer(s) per round.\n")
        print("Waiting for peers...\n")

    async def connect_to_peer(self, addr: str):
        maddr = multiaddr.Multiaddr(addr)
        info = info_from_p2p_addr(maddr)
        await self.host.connect(info)
        logger.info("Connected to peer %s", info.peer_id)

    async def _stream_handler(self, stream: INetStream):
        """Handles an INCOMING stream: another peer sending us a ModelUpdate."""
        try:
            update = await receive_model_update(stream)
            expected_w_shape = (1, self.n_features)
            expected_b_shape = (1,)
            validate_update(update, expected_w_shape, expected_b_shape)
            self.round_state.store(update)
            logger.info("Received update from %s (round %s)", update.peer_id, update.round)
        except (ValidationError, SerializationError) as e:
            logger.warning("Rejected invalid/malformed update: %s", e)
        finally:
            await stream.close()

    async def broadcast_update(self, peer_addrs: list[str], update: ModelUpdate):
        for addr in peer_addrs:
            maddr = multiaddr.Multiaddr(addr)
            info = info_from_p2p_addr(maddr)
            try:
                stream = await self.host.new_stream(info.peer_id, [PROTOCOL_ID])
                await send_model_update(stream, update)
                await stream.close()
            except Exception as e:  # noqa: BLE001 - log and continue to other peers
                logger.error("Failed to send update to %s: %s", info.peer_id, e)

    # ------------------------------------------------------------------
    # ML + FL logic
    # ------------------------------------------------------------------

    def create_model_update(self, round_number: int, weights: np.ndarray, bias: np.ndarray,
                             num_samples: int) -> ModelUpdate:
        return ModelUpdate.create(round_number, self.peer_id, num_samples, weights, bias)

    async def wait_for_round_updates(self, round_number: int, poll_interval: float = 0.25):
        """Blocks until we've received one update per expected peer, or times out."""
        with trio.move_on_after(self.round_timeout) as cancel_scope:
            while self.round_state.count_for_round(round_number) < self.expected_peers:
                await trio.sleep(poll_interval)

        if cancel_scope.cancelled_caught:
            got = self.round_state.count_for_round(round_number)
            logger.warning(
                "Round %s timed out after %.0fs: received %d/%d updates. "
                "Aggregating with whatever arrived.",
                round_number, self.round_timeout, got, self.expected_peers,
            )

    def aggregate_round(self, round_number: int, own_weights: np.ndarray, own_bias: np.ndarray,
                         own_samples: int):
        peer_updates = self.round_state.updates_for_round(round_number)
        all_updates = [
            {"weights": own_weights, "bias": own_bias, "num_samples": own_samples}
        ] + [
            {"weights": u.weights, "bias": u.bias, "num_samples": u.num_samples}
            for u in peer_updates
        ]
        return fed_avg(all_updates)

    def apply_global_model(self, weights: np.ndarray, bias: np.ndarray):
        model_lib.set_parameters(self.model, weights, bias, self.n_features)

    async def run_round(self, round_number: int, X_train, y_train, X_test, y_test,
                         peer_addrs: list[str]):
        weights, bias, local_acc = training.local_round(self.model, X_train, y_train, X_test, y_test)
        update = self.create_model_update(round_number, weights, bias, num_samples=len(X_train))

        if peer_addrs:
            await self.broadcast_update(peer_addrs, update)

        if self.expected_peers > 0:
            await self.wait_for_round_updates(round_number)
            global_weights, global_bias = self.aggregate_round(round_number, weights, bias, len(X_train))
            self.apply_global_model(global_weights, global_bias)
            global_acc = training.evaluate(self.model, X_test, y_test)
        else:
            global_acc = local_acc

        return local_acc, global_acc

    async def _run_all_rounds(self, X_train, y_train, X_test, y_test, peer_addrs: list[str]):
        for r in range(1, self.rounds + 1):
            sep = "\u2500" * 42
            print(f"{sep}\nROUND {r}\n{sep}\n")
            local_acc, global_acc = await self.run_round(r, X_train, y_train, X_test, y_test, peer_addrs)
            print(f"\nLocal accuracy:      {local_acc:.2%}")
            print(f"Federated accuracy:  {global_acc:.2%}\n")
