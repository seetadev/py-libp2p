from __future__ import (
    annotations,
)

import pytest

from libp2p.federated.payload import (
    ModelPayload,
)


def test_payload_valid_serialization() -> None:
    payload = ModelPayload(
        sender_id="QmPeer12345",
        round_id=3,
        weights=[0.1, 0.25, -0.5, 1.2],
        num_samples=100,
        metadata={"algo": "fedavg"},
    )
    raw = payload.to_bytes()
    assert isinstance(raw, bytes)

    decoded = ModelPayload.from_bytes(raw)
    assert decoded.sender_id == "QmPeer12345"
    assert decoded.round_id == 3
    assert decoded.weights == [0.1, 0.25, -0.5, 1.2]
    assert decoded.num_samples == 100
    assert decoded.metadata == {"algo": "fedavg"}


def test_payload_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="sender_id cannot be empty"):
        ModelPayload(sender_id="", round_id=0, weights=[1.0])

    with pytest.raises(ValueError, match="round_id must be non-negative"):
        ModelPayload(sender_id="p1", round_id=-1, weights=[1.0])

    with pytest.raises(ValueError, match="num_samples must be positive"):
        ModelPayload(sender_id="p1", round_id=0, weights=[1.0], num_samples=0)


def test_payload_deserialization_errors() -> None:
    with pytest.raises(ValueError, match="Failed to decode ModelPayload"):
        ModelPayload.from_bytes(b"not json")

    with pytest.raises(ValueError, match="Missing required payload keys"):
        ModelPayload.from_dict({"sender_id": "p1", "round_id": 1})

    with pytest.raises(ValueError, match="weights field must be a list"):
        bad_json = b'{"sender_id": "p1", "round_id": 1, "weights": "invalid"}'
        ModelPayload.from_bytes(bad_json)
