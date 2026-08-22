from __future__ import (
    annotations,
)

import math

import pytest

from libp2p.federated.aggregation import (
    compute_peer_variance,
    euclidean_distance,
    pairwise_mix,
    trimmed_mean,
    uniform_average,
    weighted_average,
)


def test_uniform_average() -> None:
    v1 = [1.0, 2.0, 3.0]
    v2 = [3.0, 4.0, 5.0]
    avg = uniform_average([v1, v2])
    assert avg == [2.0, 3.0, 4.0]


def test_uniform_average_empty_and_mismatched() -> None:
    with pytest.raises(ValueError, match="Cannot average empty"):
        uniform_average([])

    assert uniform_average([[], []]) == []

    with pytest.raises(ValueError, match="Dimension mismatch"):
        uniform_average([[1.0, 2.0], [1.0]])


def test_weighted_average() -> None:
    v1 = [10.0, 20.0]
    v2 = [20.0, 40.0]
    res = weighted_average([v1, v2], [1, 3])
    assert res == [17.5, 35.0]


def test_weighted_average_validation() -> None:
    with pytest.raises(ValueError, match="Vector count"):
        weighted_average([[1.0]], [1, 2])

    with pytest.raises(ValueError, match="must be positive"):
        weighted_average([[1.0]], [0])


def test_pairwise_mix() -> None:
    v1 = [0.0, 10.0]
    v2 = [10.0, 20.0]
    mixed = pairwise_mix(v1, v2, gamma=0.5)
    assert mixed == [5.0, 15.0]

    mixed_unequal = pairwise_mix(v1, v2, gamma=0.2)
    assert mixed_unequal == [2.0, 12.0]

    with pytest.raises(ValueError, match="gamma must be between"):
        pairwise_mix(v1, v2, gamma=1.5)


def test_trimmed_mean() -> None:
    vectors = [
        [0.0],
        [10.0],
        [10.0],
        [10.0],
        [100.0],
    ]
    res = trimmed_mean(vectors, trim_ratio=0.2)
    assert res == [10.0]


def test_variance_and_distance() -> None:
    v1 = [0.0, 0.0]
    v2 = [3.0, 4.0]
    assert euclidean_distance(v1, v2) == 5.0

    var = compute_peer_variance([[0.0], [10.0]])
    assert math.isclose(var, 25.0)
