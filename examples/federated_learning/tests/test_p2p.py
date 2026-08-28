"""
P2P integration test -- spins up two real libp2p hosts on localhost
loopback and checks a ModelUpdate survives the wire intact.
"""

import numpy as np
import pytest
import trio
import multiaddr
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair
from libp2p.peer.peerinfo import info_from_p2p_addr

from federated_learning.protocol import PROTOCOL_ID, receive_model_update, send_model_update
from federated_learning.serialization import ModelUpdate


@pytest.mark.trio
async def test_model_update_sent_and_received():
    received = {}

    async def handler(stream):
        update = await receive_model_update(stream)
        received["update"] = update
        await stream.close()

    host_b = new_host(key_pair=create_new_key_pair())
    async with host_b.run(listen_addrs=[multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/0")]):
        host_b.set_stream_handler(PROTOCOL_ID, handler)
        addr_b = host_b.get_addrs()[0]

        host_a = new_host(key_pair=create_new_key_pair())
        async with host_a.run(listen_addrs=[multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/0")]):
            info_b = info_from_p2p_addr(addr_b)
            await host_a.connect(info_b)

            stream = await host_a.new_stream(info_b.peer_id, [PROTOCOL_ID])
            sent_weights = np.array([[0.5, -0.5]])
            sent_bias = np.array([0.1])
            update = ModelUpdate.create(
                round_number=1,
                peer_id=str(host_a.get_id()),
                num_samples=300,
                weights=sent_weights,
                bias=sent_bias,
            )
            await send_model_update(stream, update)
            await stream.close()

            await trio.sleep(0.5)  # let the handler run

    assert "update" in received
    assert received["update"].round == 1
    assert received["update"].peer_id == str(host_a.get_id())
    assert received["update"].num_samples == 300
    assert np.allclose(received["update"].weights, sent_weights)
    assert np.allclose(received["update"].bias, sent_bias)
