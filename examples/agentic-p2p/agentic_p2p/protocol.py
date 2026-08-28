"""Byte framing + decode/validate/route.

Responsibilities of this module, and only this module:

    bytes -> message decoding -> message validation -> task/result routing

py-libp2p streams are raw byte streams with no built-in message framing, so
we use a small length-prefixed framing scheme: a 4-byte big-endian length
header followed by that many bytes of UTF-8 JSON. This keeps a single
task/result exchange independent of whatever half-close semantics a given
py-libp2p/transport version does or doesn't support.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol as TypingProtocol

from .messages import AnyMessage, MessageDecodeError, parse_message

logger = logging.getLogger(__name__)

_LEN_HEADER_BYTES = 4
_MAX_FRAME_BYTES = 5 * 1024 * 1024  # 5 MB hard cap against runaway payloads


class ByteStream(TypingProtocol):
    """The minimal subset of INetStream this module relies on.

    Kept as a Protocol so protocol.py never has to `import libp2p` directly —
    that dependency lives in peer.py only.
    """

    async def read(self, n: int = -1) -> bytes: ...
    async def write(self, data: bytes) -> None: ...


def encode_message(message: AnyMessage) -> bytes:
    """Serialize a validated message model into a length-prefixed frame."""
    payload = message.model_dump_json().encode("utf-8")
    if len(payload) > _MAX_FRAME_BYTES:
        raise ValueError("Encoded message exceeds maximum frame size")
    return len(payload).to_bytes(_LEN_HEADER_BYTES, "big") + payload


async def write_message(stream: ByteStream, message: AnyMessage) -> None:
    await stream.write(encode_message(message))


async def _read_exactly(stream: ByteStream, n: int) -> bytes:
    """Read exactly n bytes, handling streams that return partial chunks."""
    chunks: list[bytes] = []
    remaining = n
    while remaining > 0:
        chunk = await stream.read(remaining)
        if not chunk:
            raise ConnectionError("Stream closed before expected data was received")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


async def read_message(stream: ByteStream) -> AnyMessage:
    """Read one length-prefixed frame and validate it into a known message.

    Raises MessageDecodeError for malformed JSON/schema, ConnectionError if
    the stream closes mid-frame, and ValueError if the declared length is
    absurd (defense against a hostile/broken peer).
    """
    header = await _read_exactly(stream, _LEN_HEADER_BYTES)
    length = int.from_bytes(header, "big")
    if length <= 0 or length > _MAX_FRAME_BYTES:
        raise ValueError(f"Refusing to read frame of declared size {length}")

    raw = await _read_exactly(stream, length)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MessageDecodeError(f"Invalid JSON on the wire: {exc}") from exc

    if not isinstance(payload, dict):
        raise MessageDecodeError("Top-level JSON payload must be an object")

    return parse_message(payload)


class Router:
    """Routes a decoded, validated message to the right agent handler.

    Task message
         v
    protocol.py (this class)
         v
    Agent.handle_task() / Agent.handle_result() / Agent.handle_error()
    """

    def __init__(self, agent) -> None:
        self._agent = agent

    async def dispatch(self, message: AnyMessage) -> None:
        if message.type == "task":
            await self._agent.handle_task(message)
        elif message.type == "result":
            await self._agent.handle_result(message)
        elif message.type == "error":
            await self._agent.handle_error(message)
        else:  # pragma: no cover - guarded by parse_message already
            logger.warning("Received message with unroutable type: %s", message.type)
