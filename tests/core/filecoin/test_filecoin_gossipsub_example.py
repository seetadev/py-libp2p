from __future__ import annotations

import hashlib

import pytest
from multiaddr import Multiaddr
import trio

from examples.filecoin import filecoin_gossipsub_example as gossipsub_example
from libp2p import new_host
from libp2p.custom_types import ID
from libp2p.filecoin import (
    build_filecoin_gossipsub,
    build_filecoin_pubsub,
    messages_topic,
)
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.pubsub.pb import rpc_pb2
from libp2p.tools.anyio_service import background_trio_service
from libp2p.utils.address_validation import find_free_port


def test_filecoin_gossipsub_example_parser_defaults() -> None:
    parser = gossipsub_example.build_parser()
    args = parser.parse_args([])
    assert args.network == "mainnet"
    assert args.topic == "both"
    assert args.validate is True
    assert args.json is False
    assert args.verbose is False


def test_filecoin_gossipsub_example_json_payload_shape() -> None:
    snapshot = gossipsub_example._build_snapshot(
        network_alias="mainnet",
        network_name="testnetnet",
        topics=["/fil/blocks/testnetnet", "/fil/msgs/testnetnet"],
        validation_enabled=True,
        publisher_peer_id="12D3KooWPub...",
        subscriber_peer_id="12D3KooWSub...",
        received_messages=[
            {
                "topic": "/fil/blocks/testnetnet",
                "source_peer_id": "12D3KooWPub...",
                "payload_bytes": 21,
                "payload_content": "filecoin-test-message",
                "blake2b_msg_id": "abcd...",
            }
        ],
    )
    assert set(snapshot.keys()) == {
        "network_alias",
        "network_name",
        "topics",
        "gossipsub_parameters",
        "peer_score_thresholds",
        "topic_score_reference",
        "message_id_algorithm",
        "validation_enabled",
        "publisher_peer_id",
        "subscriber_peer_id",
        "received_count",
        "received_messages",
    }
    assert snapshot["gossipsub_parameters"]["degree"] == 8
    assert snapshot["gossipsub_parameters"]["degree_low"] == 6
    assert snapshot["gossipsub_parameters"]["degree_high"] == 12
    assert snapshot["message_id_algorithm"] == "blake2b-256"
    assert snapshot["received_count"] == 1


@pytest.mark.trio
async def test_filecoin_message_validation_rejects_empty_payload() -> None:
    dummy_peer = ID.from_base58("12D3KooWD2DFvDs4wekLWU8sAUJJgivbRbiiKkX9yQ3kGhuCwCqL")
    empty_msg = rpc_pb2.Message(data=b"")
    assert (
        await gossipsub_example.validate_filecoin_message_payload(dummy_peer, empty_msg)
        is False
    )
    assert (
        await gossipsub_example.validate_filecoin_block_payload(dummy_peer, empty_msg)
        is False
    )


@pytest.mark.trio
async def test_filecoin_message_validation_rejects_oversized_payload() -> None:
    dummy_peer = ID.from_base58("12D3KooWD2DFvDs4wekLWU8sAUJJgivbRbiiKkX9yQ3kGhuCwCqL")
    # Message > 256 KiB
    oversized_msg = rpc_pb2.Message(data=b"x" * (256 * 1024 + 1))
    assert (
        await gossipsub_example.validate_filecoin_message_payload(
            dummy_peer, oversized_msg
        )
        is False
    )

    # Block > 4 MiB
    oversized_block = rpc_pb2.Message(data=b"x" * (4 * 1024 * 1024 + 1))
    assert (
        await gossipsub_example.validate_filecoin_block_payload(
            dummy_peer, oversized_block
        )
        is False
    )


@pytest.mark.trio
async def test_filecoin_message_validation_accepts_valid_payload() -> None:
    dummy_peer = ID.from_base58("12D3KooWD2DFvDs4wekLWU8sAUJJgivbRbiiKkX9yQ3kGhuCwCqL")
    valid_msg = rpc_pb2.Message(data=b"valid-filecoin-transaction-payload")
    assert (
        await gossipsub_example.validate_filecoin_message_payload(dummy_peer, valid_msg)
        is True
    )
    assert (
        await gossipsub_example.validate_filecoin_block_payload(dummy_peer, valid_msg)
        is True
    )


@pytest.mark.trio
async def test_filecoin_gossipsub_local_mesh_and_blake2b_id() -> None:
    with trio.fail_after(5.0):
        snapshot = await gossipsub_example.run_demo(
            network="calibnet",
            topic_mode="blocks",
            validate=True,
            as_json=False,
        )
    assert snapshot["network_alias"] == "calibnet"
    assert snapshot["received_count"] == 1

    received = snapshot["received_messages"][0]
    expected_data = b"filecoin-test-message"  # 21 bytes
    expected_blake2b = hashlib.blake2b(expected_data, digest_size=32).hexdigest()

    assert received["payload_bytes"] == 21
    assert received["payload_content"] == "filecoin-test-message"
    assert received["blake2b_msg_id"] == expected_blake2b


@pytest.mark.trio
async def test_filecoin_gossipsub_validation_filters_invalid_message() -> None:
    with trio.fail_after(6.0):
        network_name = "calibrationnet"
        m_topic = messages_topic(network_name)

        port_a = find_free_port()
        port_b = find_free_port()
        addr_a = Multiaddr(f"/ip4/127.0.0.1/tcp/{port_a}")
        addr_b = Multiaddr(f"/ip4/127.0.0.1/tcp/{port_b}")

        host_a = new_host(listen_addrs=[addr_a])
        host_b = new_host(listen_addrs=[addr_b])

        gossipsub_a = build_filecoin_gossipsub(network_name=network_name)
        gossipsub_b = build_filecoin_gossipsub(network_name=network_name)

        pubsub_a = build_filecoin_pubsub(
            host=host_a, gossipsub=gossipsub_a, network_name=network_name
        )
        pubsub_b = build_filecoin_pubsub(
            host=host_b, gossipsub=gossipsub_b, network_name=network_name
        )

        # Attach async validator on host_b that rejects oversized payloads (> 256 KiB)
        pubsub_b.set_topic_validator(
            m_topic,
            gossipsub_example.validate_filecoin_message_payload,
            is_async_validator=True,
        )

        received: list[bytes] = []

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

                    peer_info_b = info_from_p2p_addr(host_b.get_addrs()[0])
                    await host_a.connect(peer_info_b)

                    sub = await pubsub_b.subscribe(m_topic)
                    await trio.sleep(0.2)

                    async def _reader() -> None:
                        with trio.move_on_after(1.0):
                            msg = await sub.get()
                            received.append(msg.data)

                    async with trio.open_nursery() as nursery:
                        nursery.start_soon(_reader)
                        await trio.sleep(0.1)

                        # 1. Publish invalid oversized payload (>256 KiB)
                        oversized_payload = b"x" * (256 * 1024 + 10)
                        await pubsub_a.publish(m_topic, oversized_payload)
                        await trio.sleep(0.3)

                        # 2. Publish valid payload
                        valid_payload = b"valid-filecoin-msg"
                        await pubsub_a.publish(m_topic, valid_payload)
                        await trio.sleep(0.3)

                        nursery.cancel_scope.cancel()

        # The subscriber should only receive the valid payload
        assert len(received) == 1
        assert received[0] == b"valid-filecoin-msg"
