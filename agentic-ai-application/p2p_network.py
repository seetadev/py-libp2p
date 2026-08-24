import uuid

import multiaddr
import trio
from libp2p import new_host
from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.peer.peerinfo import info_from_p2p_addr

from .config import CONNECTION_TIMEOUT, P2P_TIMEOUT, PROTOCOL_ID
from .protocol import receive_frame, send_frame


def get_tcp_address(host):
    for address in host.get_addrs():
        if "/tcp/" in str(address):
            return multiaddr.Multiaddr(str(address))

    raise RuntimeError("No TCP address available.")


class P2PNetwork:
    def __init__(self, hosts):
        self.hosts = hosts

    async def open_stream(self, source_id, target_id):
        source = self.hosts[source_id]
        target = self.hosts[target_id]

        address = multiaddr.Multiaddr(
            f"{get_tcp_address(target)}/p2p/{target.get_id()}"
        )

        info = info_from_p2p_addr(address)

        with trio.move_on_after(CONNECTION_TIMEOUT) as scope:
            await source.connect(info)
            stream = await source.new_stream(
                target.get_id(),
                [PROTOCOL_ID],
            )

        if scope.cancelled_caught:
            raise TimeoutError(
                f"P2P connection failed: "
                f"{source_id} -> {target_id}"
            )

        return stream


async def send_agent_request(
    network,
    source_id,
    target_id,
    prompt,
    state,
    personas,
):
    source = personas[source_id]

    operation = await state.add(
        agent_id=source.agent_id,
        agent_name=source.name,
        role="request",
        content=prompt,
    )

    stream = await network.open_stream(
        source_id,
        target_id,
    )

    try:
        await send_frame(
            stream,
            {
                "type": "agent_request",
                "request_id": str(uuid.uuid4()),
                "source_agent": source_id,
                "target_agent": target_id,
                "operation": operation,
            },
        )

        with trio.move_on_after(P2P_TIMEOUT) as scope:
            response = await receive_frame(stream)

        if scope.cancelled_caught:
            raise TimeoutError("P2P response timed out.")

        if response.get("type") == "error":
            raise RuntimeError(
                response.get(
                    "content",
                    "Remote agent failed.",
                )
            )

        if response.get("type") != "agent_response":
            raise RuntimeError(
                f"Unexpected response: "
                f"{response.get('type')}"
            )

        result = response["operation"]

        await state.merge(result)

        return result

    finally:
        await stream.close()


async def send_agent_operation(
    network,
    source_id,
    target_id,
    operation,
):
    stream = await network.open_stream(
        source_id,
        target_id,
    )

    try:
        await send_frame(
            stream,
            {
                "type": "state_sync",
                "operation": operation,
            },
        )

        with trio.move_on_after(P2P_TIMEOUT) as scope:
            response = await receive_frame(stream)

        if scope.cancelled_caught:
            raise TimeoutError(
                "P2P synchronization timed out."
            )

        if response.get("type") != "sync_ack":
            raise RuntimeError(
                "Unexpected synchronization response: "
                f"{response.get('type')}"
            )

    finally:
        await stream.close()


def create_agent_host(
    persona,
    state,
    llm,
    ethercalc,
    personas,
):
    host = new_host(
        key_pair=create_new_key_pair(),
        enable_tcp=True,
        enable_quic=False,
    )

    async def handler(stream):
        from .agent import handle_incoming_request

        await handle_incoming_request(
            stream,
            persona,
            state,
            llm,
            ethercalc,
            personas,
        )

    host.set_stream_handler(
        PROTOCOL_ID,
        handler,
    )

    return host
