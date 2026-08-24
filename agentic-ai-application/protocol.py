import json
import struct

from .config import MAX_FRAME_SIZE


async def read_exact(stream, size):
    data = bytearray()

    while len(data) < size:
        chunk = await stream.read(size - len(data))

        if not chunk:
            raise ConnectionError("Peer closed the stream.")

        data.extend(chunk)

    return bytes(data)


async def send_frame(stream, message):
    payload = json.dumps(
        message,
        ensure_ascii=False,
    ).encode()

    if len(payload) > MAX_FRAME_SIZE:
        raise ValueError("P2P frame too large.")

    await stream.write(
        struct.pack("!I", len(payload)) + payload
    )


async def receive_frame(stream):
    size = struct.unpack(
        "!I",
        await read_exact(stream, 4),
    )[0]

    if not 0 < size <= MAX_FRAME_SIZE:
        raise ValueError("Invalid P2P frame size.")

    message = json.loads(
        (await read_exact(stream, size)).decode()
    )

    if not isinstance(message, dict):
        raise ValueError("P2P message must be an object.")

    return message
