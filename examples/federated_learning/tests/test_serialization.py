import numpy as np
import pytest

from federated_learning.serialization import ModelUpdate, SerializationError, deserialize_update, serialize_update


def test_round_trip():
    original = ModelUpdate.create(
        round_number=1,
        peer_id="12D3KooWTest",
        num_samples=300,
        weights=np.array([[0.1, 0.2, 0.3]]),
        bias=np.array([0.05]),
    )
    data = serialize_update(original)
    decoded = deserialize_update(data)

    assert decoded.round == original.round
    assert decoded.peer_id == original.peer_id
    assert decoded.num_samples == original.num_samples
    assert np.allclose(decoded.weights, original.weights)
    assert np.allclose(decoded.bias, original.bias)


def test_serialized_bytes_are_newline_terminated():
    update = ModelUpdate.create(1, "peer-a", 100, np.array([[0.1]]), np.array([0.0]))
    data = serialize_update(update)
    assert data.endswith(b"\n")


def test_deserialize_malformed_json_raises():
    with pytest.raises(SerializationError):
        deserialize_update(b"not valid json\n")


def test_deserialize_missing_fields_raises():
    with pytest.raises(SerializationError):
        deserialize_update(b'{"type": "model_update", "round": 1}\n')


def test_deserialize_non_object_json_raises():
    with pytest.raises(SerializationError):
        deserialize_update(b"[1, 2, 3]\n")
