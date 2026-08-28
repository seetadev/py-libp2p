"""
protocol.py
-----------
Custom libp2p protocol: /ml/federated-learning/1.0.0

Handles the newline-delimited JSON framing over a raw libp2p stream,
plus message validation. Never trust bytes coming off the network:
every field is checked before it touches the aggregator.
"""

from __future__ import annotations

import numpy as np
from libp2p.custom_types import TProtocol
from libp2p.network.stream.net_stream import INetStream

from .serialization import ModelUpdate, SerializationError, deserialize_update, serialize_update

PROTOCOL_ID = TProtocol("/ml/federated-learning/1.0.0")

MAX_MESSAGE_BYTES = 10 * 1024 * 1024  # 10 MB safety cap against a runaway/malicious peer


class ValidationError(ValueError):
    pass


def validate_update(update: ModelUpdate, expected_weight_shape: tuple, expected_bias_shape: tuple) -> None:
    """Raises ValidationError on anything that doesn't look like a well-formed update."""
    if update.type != "model_update":
        raise ValidationError(f"Unexpected message type: {update.type!r}")
    if not isinstance(update.round, int) or update.round < 0:
        raise ValidationError(f"Invalid round: {update.round!r}")
    if not isinstance(update.num_samples, int) or update.num_samples <= 0:
        raise ValidationError(f"Invalid num_samples: {update.num_samples!r}")
    if not update.peer_id:
        raise ValidationError("Missing peer_id")

    try:
        w = np.array(update.weights, dtype=float)
        b = np.array(update.bias, dtype=float)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Non-numeric weights/bias: {e}") from e

    if not np.all(np.isfinite(w)) or not np.all(np.isfinite(b)):
        raise ValidationError("Weights/bias contain NaN or infinite values.")

    if w.shape != expected_weight_shape:
        raise ValidationError(f"Weight shape mismatch: expected {expected_weight_shape}, got {w.shape}")
    if b.shape != expected_bias_shape:
        raise ValidationError(f"Bias shape mismatch: expected {expected_bias_shape}, got {b.shape}")


async def read_one_message(stream: INetStream) -> bytes:
    """Read a single newline-delimited message from the stream."""
    buf = bytearray()
    while True:
        chunk = await stream.read(1)
        if not chunk:
            break
        buf += chunk
        if buf.endswith(b"\n"):
            break
        if len(buf) > MAX_MESSAGE_BYTES:
            raise ValidationError("Message exceeds max size; dropping connection.")
    return bytes(buf)


async def send_model_update(stream: INetStream, update: ModelUpdate) -> None:
    data = serialize_update(update)
    await stream.write(data)


async def receive_model_update(stream: INetStream) -> ModelUpdate:
    raw = await read_one_message(stream)
    if not raw:
        raise SerializationError("Empty message received (peer closed stream early).")
    return deserialize_update(raw)
