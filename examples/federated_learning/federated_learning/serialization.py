"""
serialization.py
-----------------
ModelUpdate <-> newline-delimited JSON bytes.

Wire format per message (see protocol.py for framing over the stream):
    {"type": "model_update", "round": 1, "peer_id": "...",
     "num_samples": 300, "weights": [[...]], "bias": [...]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

REQUIRED_FIELDS = {"type", "round", "peer_id", "num_samples", "weights", "bias"}


class SerializationError(ValueError):
    pass


@dataclass
class ModelUpdate:
    type: str
    round: int
    peer_id: str
    num_samples: int
    weights: list
    bias: list

    @classmethod
    def create(cls, round_number: int, peer_id: str, num_samples: int,
               weights: np.ndarray, bias: np.ndarray) -> "ModelUpdate":
        return cls(
            type="model_update",
            round=round_number,
            peer_id=peer_id,
            num_samples=num_samples,
            weights=np.array(weights).tolist(),
            bias=np.array(bias).tolist(),
        )


def serialize_update(update: ModelUpdate) -> bytes:
    payload = {
        "type": update.type,
        "round": update.round,
        "peer_id": update.peer_id,
        "num_samples": update.num_samples,
        "weights": update.weights,
        "bias": update.bias,
    }
    line = json.dumps(payload) + "\n"
    return line.encode("utf-8")


def deserialize_update(data: bytes) -> ModelUpdate:
    try:
        text = data.decode("utf-8").strip()
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SerializationError(f"Malformed message: {e}") from e

    if not isinstance(payload, dict):
        raise SerializationError(f"Expected a JSON object, got {type(payload).__name__}")

    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        raise SerializationError(f"Missing fields: {sorted(missing)}")

    return ModelUpdate(
        type=payload["type"],
        round=payload["round"],
        peer_id=payload["peer_id"],
        num_samples=payload["num_samples"],
        weights=payload["weights"],
        bias=payload["bias"],
    )
