import pytest
from multiaddr import (
    Multiaddr,
)
import trio

from libp2p.network.connection.raw_connection import (
    RawConnection,
)
from libp2p.tools.constants import (
    LISTEN_MADDR,
)
from libp2p.transport.exceptions import (
    OpenConnectionError,
)
from libp2p.transport.tcp.tcp import (
    TCP,
)


@pytest.mark.trio
async def test_tcp_listener(nursery):
    transport = TCP()

    async def handler(tcp_stream):
        pass

    listener = transport.create_listener(handler)
    assert len(listener.get_addrs()) == 0
    await listener.listen(LISTEN_MADDR, nursery)
    assert len(listener.get_addrs()) == 1
    await listener.listen(LISTEN_MADDR, nursery)
    assert len(listener.get_addrs()) == 2

@pytest.mark.trio
async def test_tcp_listener_dns4(nursery):
    transport = TCP()

    async def handler(stream):
        # We're not using the stream for this test
        pass

    dns4_maddr = Multiaddr("/dns4/localhost/tcp/0")
    listener = transport.create_listener(handler)

    await listener.listen(dns4_maddr, nursery)
    addrs = listener.get_addrs()

    assert len(addrs) == 1
    addr_str = str(addrs[0])

    # Check that DNS4 resolved to a valid IP-based addr
    assert addr_str.startswith(("/ip4/127.0.0.1/tcp/", "/ip6/::1/tcp/"))

@pytest.mark.trio
async def test_tcp_dial(nursery):
    transport = TCP()
    raw_conn_other_side: RawConnection | None = None
    event = trio.Event()

    async def handler(tcp_stream):
        print("🔥 Handler triggered!")
        nonlocal raw_conn_other_side
        raw_conn_other_side = RawConnection(tcp_stream, False)
        event.set()
        await trio.sleep_forever()

    # Test: `OpenConnectionError` is raised when trying to dial to a port which
    #   no one is not listening to.
    with pytest.raises(OpenConnectionError):
        print("✅ Listener is up and running.")
        await transport.dial(Multiaddr("/ip4/127.0.0.1/tcp/1"))

    listener = transport.create_listener(handler)
    await listener.listen(LISTEN_MADDR, nursery)
    addrs = listener.get_addrs()
    assert len(addrs) == 1
    listen_addr = addrs[0]
    raw_conn = await transport.dial(listen_addr)
    await event.wait()

    data = b"123"
    assert raw_conn_other_side is not None
    await raw_conn_other_side.write(data)
    assert (await raw_conn.read(len(data))) == data

@pytest.mark.trio
async def test_tcp_dial_dns4(nursery):
    transport = TCP()
    connection_made = trio.Event()
    received_data = []

    async def connection_handler(stream):
        try:
            data = await stream.read(1024)
            if data:  # Only track real messages
                received_data.append(data)
            await stream.write(data)
        finally:
            await stream.close()

    listener = transport.create_listener(connection_handler)
    dns_maddr = Multiaddr("/dns4/localhost/tcp/0")
    assert await listener.listen(dns_maddr, nursery)

    listen_addrs = listener.get_addrs()
    listen_port = listen_addrs[0].value_for_protocol("tcp")
    dial_maddr = Multiaddr(f"/dns4/localhost/tcp/{listen_port}")

    async def dial_task():
        connection_made.set()
        conn = await transport.dial(dial_maddr)
        await conn.write(b"test123")
        response = await conn.read(1024)
        assert response == b"test123"
        await conn.close()

    async with trio.open_nursery() as conn_nursery:
        conn_nursery.start_soon(dial_task)
        await connection_made.wait()

    assert received_data == [b"test123"]
    await listener.close()