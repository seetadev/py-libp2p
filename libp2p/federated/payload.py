from __future__ import (
    annotations,
)

import dataclasses
import json
from typing import (
    Any,
)


@dataclasses.dataclass(frozen=True)
class ModelPayload:
    """Message payload for model weight updates over pubsub."""

    sender_id: str
    round_id: int
    weights: list[float]
    num_samples: int = 1
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.sender_id:
            raise ValueError("sender_id cannot be empty")
        if self.round_id < 0:
            raise ValueError("round_id must be non-negative")
        if not isinstance(self.weights, (list, tuple)):
            raise ValueError("weights must be a sequence of numbers")
        if self.num_samples <= 0:
            raise ValueError("num_samples must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender_id": self.sender_id,
            "round_id": self.round_id,
            "weights": list(self.weights),
            "num_samples": self.num_samples,
            "metadata": self.metadata,
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelPayload:
        if not isinstance(data, dict):
            raise ValueError("Payload must be a dictionary")

        required = {"sender_id", "round_id", "weights"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing required payload keys: {missing}")

        weights = data["weights"]
        if not isinstance(weights, (list, tuple)):
            raise ValueError("weights field must be a list of numbers")

        return cls(
            sender_id=str(data["sender_id"]),
            round_id=int(data["round_id"]),
            weights=[float(w) for w in weights],
            num_samples=int(data.get("num_samples", 1)),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> ModelPayload:
        try:
            return cls.from_dict(json.loads(raw.decode("utf-8")))
        except Exception as exc:
            raise ValueError(f"Failed to decode ModelPayload: {exc}") from exc
