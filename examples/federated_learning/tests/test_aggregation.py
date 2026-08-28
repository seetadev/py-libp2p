import numpy as np
import pytest

from federated_learning.aggregation import AggregationError, fed_avg, simple_average


def test_simple_average_two_models():
    updates = [
        {"weights": [[1, 2]], "bias": [0], "num_samples": 1},
        {"weights": [[3, 4]], "bias": [0], "num_samples": 1},
    ]
    w, b = simple_average(updates)
    assert np.allclose(w, [[2, 3]])


def test_weighted_fed_avg():
    updates = [
        {"weights": [[0.2]], "bias": [0.0], "num_samples": 100},
        {"weights": [[0.8]], "bias": [0.0], "num_samples": 900},
    ]
    w, b = fed_avg(updates)
    assert np.allclose(w, [[0.74]], atol=1e-6)


def test_fed_avg_matches_manual_three_peers():
    updates = [
        {"weights": [[1.0]], "bias": [0.5], "num_samples": 200},
        {"weights": [[2.0]], "bias": [1.0], "num_samples": 300},
        {"weights": [[3.0]], "bias": [1.5], "num_samples": 500},
    ]
    w, b = fed_avg(updates)
    expected_w = (200 * 1.0 + 300 * 2.0 + 500 * 3.0) / 1000
    expected_b = (200 * 0.5 + 300 * 1.0 + 500 * 1.5) / 1000
    assert np.allclose(w, [[expected_w]])
    assert np.allclose(b, [expected_b])


def test_shape_mismatch_rejected():
    updates = [
        {"weights": [[1, 2]], "bias": [0], "num_samples": 10},
        {"weights": [[1, 2, 3]], "bias": [0], "num_samples": 10},
    ]
    with pytest.raises(AggregationError):
        fed_avg(updates)


def test_empty_update_list_rejected():
    with pytest.raises(AggregationError):
        fed_avg([])


def test_invalid_num_samples_rejected():
    updates = [{"weights": [[1]], "bias": [0], "num_samples": 0}]
    with pytest.raises(AggregationError):
        fed_avg(updates)


def test_negative_num_samples_rejected():
    updates = [{"weights": [[1]], "bias": [0], "num_samples": -5}]
    with pytest.raises(AggregationError):
        fed_avg(updates)


def test_non_numeric_weights_rejected():
    updates = [{"weights": [["a", "b"]], "bias": [0], "num_samples": 10}]
    with pytest.raises(AggregationError):
        fed_avg(updates)
