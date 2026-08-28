import numpy as np
import pytest

from federated_learning.protocol import ValidationError, validate_update
from federated_learning.serialization import ModelUpdate


def _valid_update(**overrides):
    base = dict(
        type="model_update",
        round=1,
        peer_id="12D3KooWTest",
        num_samples=100,
        weights=[[0.1, 0.2]],
        bias=[0.0],
    )
    base.update(overrides)
    return ModelUpdate(**base)


def test_valid_update_passes():
    update = _valid_update()
    validate_update(update, expected_weight_shape=(1, 2), expected_bias_shape=(1,))


def test_wrong_type_rejected():
    update = _valid_update(type="hello")
    with pytest.raises(ValidationError):
        validate_update(update, (1, 2), (1,))


def test_negative_round_rejected():
    update = _valid_update(round=-1)
    with pytest.raises(ValidationError):
        validate_update(update, (1, 2), (1,))


def test_zero_num_samples_rejected():
    update = _valid_update(num_samples=0)
    with pytest.raises(ValidationError):
        validate_update(update, (1, 2), (1,))


def test_missing_peer_id_rejected():
    update = _valid_update(peer_id="")
    with pytest.raises(ValidationError):
        validate_update(update, (1, 2), (1,))


def test_wrong_weight_shape_rejected():
    update = _valid_update(weights=[[0.1, 0.2, 0.3]])
    with pytest.raises(ValidationError):
        validate_update(update, expected_weight_shape=(1, 2), expected_bias_shape=(1,))


def test_nan_weights_rejected():
    update = _valid_update(weights=[[float("nan"), 0.2]])
    with pytest.raises(ValidationError):
        validate_update(update, (1, 2), (1,))
