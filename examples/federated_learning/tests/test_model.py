import numpy as np
import pytest

from federated_learning import model as model_lib
from federated_learning.dataset import generate_global_dataset


def test_model_trains_and_extracts_params():
    X, y = generate_global_dataset(n_samples=100, n_features=5, seed=1)
    m = model_lib.new_model(seed=1)
    m.fit(X, y)
    weights, bias = model_lib.get_parameters(m)
    assert weights.shape == (1, 5)
    assert bias.shape == (1,)


def test_get_parameters_before_fit_raises():
    m = model_lib.new_model(seed=1)
    with pytest.raises(RuntimeError):
        model_lib.get_parameters(m)


def test_set_parameters_round_trips():
    X, y = generate_global_dataset(n_samples=100, n_features=5, seed=1)
    m = model_lib.new_model(seed=1)
    m.fit(X, y)
    w, b = model_lib.get_parameters(m)

    m2 = model_lib.new_model(seed=1)
    model_lib.set_parameters(m2, w, b, n_features=5)
    w2, b2 = model_lib.get_parameters(m2)

    assert np.allclose(w, w2)
    assert np.allclose(b, b2)


def test_set_parameters_shape_mismatch_raises():
    m = model_lib.new_model(seed=1)
    model_lib.ensure_initialized(m, n_features=5)
    with pytest.raises(ValueError):
        model_lib.set_parameters(m, np.zeros((1, 3)), np.zeros(1), n_features=5)


def test_ensure_initialized_is_idempotent():
    X, y = generate_global_dataset(n_samples=50, n_features=4, seed=2)
    m = model_lib.new_model(seed=2)
    m.fit(X, y)
    w_before, b_before = model_lib.get_parameters(m)
    model_lib.ensure_initialized(m, n_features=4)
    w_after, b_after = model_lib.get_parameters(m)
    assert np.allclose(w_before, w_after)
    assert np.allclose(b_before, b_after)
