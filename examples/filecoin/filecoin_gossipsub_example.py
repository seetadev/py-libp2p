"""
Filecoin-compatible GossipSub reference example.

Demonstrates:
1. Setting up local peers using Filecoin GossipSub presets (D=8, D_lo=6, D_hi=12).
2. Subscribing to Filecoin topics (/fil/blocks/<network>, /fil/msgs/<network>).
3. Deterministic Blake2b-256 message ID generation (filecoin_message_id).
4. Topic message validation (rejecting empty or oversized payloads).
5. Local loopback message publishing and reception in < 2 seconds.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from multiaddr import Multiaddr
import trio

from libp2p import new_host
from libp2p.custom_types import ID
from libp2p.filecoin import (
    FILECOIN_PEER_SCORE_REFERENCE,
    FILECOIN_TOPIC_SCORE_REFERENCE,
    blocks_topic,
    build_filecoin_gossipsub,
    build_filecoin_pubsub,
    filecoin_message_id,
    get_network_preset,
    messages_topic,
)
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.pubsub.pb import rpc_pb2
from libp2p.tools.anyio_service import background_trio_service
from libp2p.utils.address_validation import find_free_port

logger = logging.getLogger("filecoin_gossipsub_example")

# Filecoin message validation size limits (Lotus / Forest parity)
MAX_FILECOIN_MESSAGE_SIZE = 256 * 1024  # 256 KiB for /fil/msgs
MAX_FILECOIN_BLOCK_SIZE = 4 * 1024 * 1024  # 4 MiB for /fil/blocks


async def validate_filecoin_message_payload(peer_id: ID, msg: rpc_pb2.Message) -> bool:
    """
    Asynchronously validate incoming Filecoin transaction message.

    In full Filecoin client implementations (Lotus, Forest), message
    validation checks signature validity and gas parameters against
    the current chain state. At the pubsub transport layer, validators
    first enforce strict payload bounds:
    - Rejects empty payloads (len == 0)
    - Rejects oversized payloads (> 256 KiB)

    Using an async validator allows integration with non-blocking state
    checks and exercises py-libp2p's async validator semaphore & timeout.
    All internal exceptions are caught to prevent crashing the Trio nursery.
    """
    try:
        if not msg.data or len(msg.data) == 0:
            logger.warning(
                "Rejected empty Filecoin message payload from peer %s", peer_id
            )
            return False
        if len(msg.data) > MAX_FILECOIN_MESSAGE_SIZE:
            logger.warning(
                "Rejected oversized Filecoin message (%d bytes > %d limit) from %s",
                len(msg.data),
                MAX_FILECOIN_MESSAGE_SIZE,
                peer_id,
            )
            return False
        return True
    except Exception as exc:
        logger.warning(
            "Exception during Filecoin message validation from %s: %s",
            peer_id,
            exc,
        )
        return False


async def validate_filecoin_block_payload(peer_id: ID, msg: rpc_pb2.Message) -> bool:
    """
    Asynchronously validate incoming Filecoin block payload.

    Rejects:
    - Empty payloads (len == 0)
    - Oversized payloads (> 4 MiB)

    Catches and isolates exceptions to maintain transport stability.
    """
    try:
        if not msg.data or len(msg.data) == 0:
            logger.warning(
                "Rejected empty Filecoin block payload from peer %s", peer_id
            )
            return False
        if len(msg.data) > MAX_FILECOIN_BLOCK_SIZE:
            logger.warning(
                "Rejected oversized Filecoin block (%d bytes > %d limit) from %s",
                len(msg.data),
                MAX_FILECOIN_BLOCK_SIZE,
                peer_id,
            )
            return False
        return True
    except Exception as exc:
        logger.warning(
            "Exception during Filecoin block validation from %s: %s",
            peer_id,
            exc,
        )
        return False


def _selected_topics(topic_mode: str, network_name: str) -> list[str]:
    if topic_mode == "blocks":
        return [blocks_topic(network_name)]
    if topic_mode == "messages":
        return [messages_topic(network_name)]
    return [blocks_topic(network_name), messages_topic(network_name)]


def _build_snapshot(
    network_alias: str,
    network_name: str,
    topics: list[str],
    validation_enabled: bool,
    publisher_peer_id: str,
    subscriber_peer_id: str,
    received_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "network_alias": network_alias,
        "network_name": network_name,
        "topics": {
            "blocks": blocks_topic(network_name),
            "messages": messages_topic(network_name),
            "selected": list(topics),
        },
        "gossipsub_parameters": {
            "degree": 8,
            "degree_low": 6,
            "degree_high": 12,
            "heartbeat_interval_sec": 1.0,
            "history_length": 10,
            "gossip_window": 3,
            "prune_backoff_sec": 60,
        },
        # Runtime Scoring Note:
        # FILECOIN_PEER_SCORE_REFERENCE defines static baseline GossipSub
        # thresholds (publish, gossip, graylist, accept_px, opportunistic_graft)
        # passed into ScoreParams. In production nodes (Lotus/Forest), dynamic
        # topic scoring, delivery rate tracking (P1-P4), and decay intervals are
        # calculated continuously at runtime. In py-libp2p, ScoreParams enforces
        # threshold gating, pruning, and opportunistic grafting.
        "peer_score_thresholds": FILECOIN_PEER_SCORE_REFERENCE,
        "topic_score_reference": FILECOIN_TOPIC_SCORE_REFERENCE,
        "message_id_algorithm": "blake2b-256",
        "validation_enabled": validation_enabled,
        "publisher_peer_id": publisher_peer_id,
        "subscriber_peer_id": subscriber_peer_id,
        "received_count": len(received_messages),
        "received_messages": received_messages,
    }


async def run_demo(
    network: str = "mainnet",
    topic_mode: str = "both",
    validate: bool = True,
    as_json: bool = False,
) -> dict[str, Any]:
    # Resolve the Filecoin network preset. Upstream Lotus uses historical
    # genesis string "testnetnet" for mainnet and "calibrationnet" for calibnet.
    preset = get_network_preset(network)
    network_name = preset.genesis_network_name
    topics = _selected_topics(topic_mode, network_name)

    port_a = find_free_port()
    port_b = find_free_port()
    addr_a = Multiaddr(f"/ip4/127.0.0.1/tcp/{port_a}")
    addr_b = Multiaddr(f"/ip4/127.0.0.1/tcp/{port_b}")

    host_a = new_host(listen_addrs=[addr_a])
    host_b = new_host(listen_addrs=[addr_b])

    gossipsub_a = build_filecoin_gossipsub(network_name=network_name)
    gossipsub_b = build_filecoin_gossipsub(network_name=network_name)

    # Build Filecoin pubsub instances using deterministic blake2b message ID.
    # Note: filecoin_message_id hashes raw payload bytes (msg.data) for pubsub
    # deduplication/scoring; distinct from application-level CBOR message CIDs.
    pubsub_a = build_filecoin_pubsub(
        host=host_a, gossipsub=gossipsub_a, network_name=network_name
    )
    pubsub_b = build_filecoin_pubsub(
        host=host_b, gossipsub=gossipsub_b, network_name=network_name
    )

    # Attach Filecoin async topic validators to host_b if validation is requested
    if validate:
        b_topic = blocks_topic(network_name)
        m_topic = messages_topic(network_name)
        pubsub_b.set_topic_validator(
            b_topic, validate_filecoin_block_payload, is_async_validator=True
        )
        pubsub_b.set_topic_validator(
            m_topic, validate_filecoin_message_payload, is_async_validator=True
        )

    received_messages: list[dict[str, Any]] = []

    async with host_a.run(listen_addrs=[addr_a]), host_b.run(listen_addrs=[addr_b]):
        async with (
            background_trio_service(pubsub_a),
            background_trio_service(gossipsub_a),
        ):
            async with (
                background_trio_service(pubsub_b),
                background_trio_service(gossipsub_b),
            ):
                await pubsub_a.wait_until_ready()
                await pubsub_b.wait_until_ready()

                # Connect host_a (publisher) to host_b (subscriber)
                listen_addr_b = host_b.get_addrs()[0]
                peer_info_b = info_from_p2p_addr(listen_addr_b)
                await host_a.connect(peer_info_b)

                # Subscribe host_b to chosen topics
                subscriptions = {}
                for topic in topics:
                    subscriptions[topic] = await pubsub_b.subscribe(topic)

                # Small delay for mesh connection to stabilize
                await trio.sleep(0.2)

                # Helper to listen for a message on a topic with timeout
                async def _receive_from_topic(topic: str, sub: Any) -> None:
                    try:
                        with trio.move_on_after(1.5):
                            msg = await sub.get()
                            # Compute deterministic Blake2b-256 message ID
                            msg_id_bytes = filecoin_message_id(msg)
                            msg_id_hex = msg_id_bytes.hex()
                            payload_data = (
                                msg.data if isinstance(msg.data, bytes) else b""
                            )

                            record = {
                                "topic": topic,
                                "source_peer_id": str(host_a.get_id()),
                                "payload_bytes": len(payload_data),
                                "payload_content": payload_data.decode(
                                    "utf-8", errors="replace"
                                ),
                                "blake2b_msg_id": msg_id_hex,
                            }
                            received_messages.append(record)
                    except Exception as exc:
                        logger.debug("Receive error on %s: %s", topic, exc)

                async with trio.open_nursery() as nursery:
                    for topic, sub in subscriptions.items():
                        nursery.start_soon(_receive_from_topic, topic, sub)

                    # Wait a moment for subscription handlers to be active
                    await trio.sleep(0.1)

                    # Publish a 21-byte test message to each selected topic
                    for topic in topics:
                        test_payload = b"filecoin-test-message"  # 21 bytes
                        await pubsub_a.publish(topic, test_payload)

                    await trio.sleep(0.3)
                    nursery.cancel_scope.cancel()

    snapshot = _build_snapshot(
        network_alias=network,
        network_name=network_name,
        topics=topics,
        validation_enabled=validate,
        publisher_peer_id=str(host_a.get_id()),
        subscriber_peer_id=str(host_b.get_id()),
        received_messages=received_messages,
    )

    if as_json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        print("=" * 60)
        print("Filecoin GossipSub Reference Example")
        print("=" * 60)
        print(f"Network: {network} (upstream: {network_name})")
        print(f"Publisher:  {host_a.get_id()}")
        print(f"Subscriber: {host_b.get_id()}")
        print(f"Validation: {'Enabled (async)' if validate else 'Disabled'}")
        print(f"Topics:     {', '.join(topics)}")
        print("-" * 60)
        print("Received Messages:")
        for idx, rec in enumerate(received_messages, start=1):
            p_len = rec["payload_bytes"]
            print(f"[{idx}] Topic: {rec['topic']}")
            print(f"    Payload: {rec['payload_content']} ({p_len} bytes)")
            print(f"    Blake2b Message ID: {rec['blake2b_msg_id']}")
        print("=" * 60)

    return snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Filecoin-compatible GossipSub local reference example.",
    )
    parser.add_argument(
        "--network",
        choices=("mainnet", "calibnet"),
        default="mainnet",
        help="Filecoin network alias (default: mainnet).",
    )
    parser.add_argument(
        "--topic",
        choices=("blocks", "messages", "both"),
        default="both",
        help="Which Filecoin gossip topics to demonstrate.",
    )
    parser.add_argument(
        "--validate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable Filecoin topic message validation (default: True).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output configuration and received message snapshot as JSON.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    trio.run(run_demo, args.network, args.topic, args.validate, args.json)


if __name__ == "__main__":
    main()
