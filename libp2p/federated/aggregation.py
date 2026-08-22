from __future__ import (
    annotations,
)

from collections.abc import (
    Sequence,
)
import math


def uniform_average(weight_vectors: Sequence[Sequence[float]]) -> list[float]:
    """Compute element-wise arithmetic mean across weight vectors."""
    if not weight_vectors:
        raise ValueError("Cannot average empty collection of weight vectors")

    num_vectors = len(weight_vectors)
    dim = len(weight_vectors[0])
    if dim == 0:
        return []

    for i, vec in enumerate(weight_vectors):
        if len(vec) != dim:
            raise ValueError(
                f"Dimension mismatch at index {i}: expected {dim}, got {len(vec)}"
            )

    sums = [0.0] * dim
    for vec in weight_vectors:
        for j in range(dim):
            sums[j] += float(vec[j])

    return [s / num_vectors for s in sums]


def weighted_average(
    weight_vectors: Sequence[Sequence[float]],
    sample_counts: Sequence[int],
) -> list[float]:
    """Compute element-wise weighted average based on peer sample counts."""
    if not weight_vectors:
        raise ValueError("Cannot average empty collection of weight vectors")
    if len(weight_vectors) != len(sample_counts):
        raise ValueError(
            f"Vector count ({len(weight_vectors)}) != "
            f"sample count ({len(sample_counts)})"
        )

    for i, count in enumerate(sample_counts):
        if count <= 0:
            raise ValueError(f"Sample count at index {i} must be positive, got {count}")

    total_samples = sum(sample_counts)
    dim = len(weight_vectors[0])
    if dim == 0:
        return []

    for i, vec in enumerate(weight_vectors):
        if len(vec) != dim:
            raise ValueError(
                f"Dimension mismatch at index {i}: expected {dim}, got {len(vec)}"
            )

    result = [0.0] * dim
    for vec, count in zip(weight_vectors, sample_counts):
        scale = count / total_samples
        for j in range(dim):
            result[j] += float(vec[j]) * scale

    return result


def pairwise_mix(
    local_weights: Sequence[float],
    remote_weights: Sequence[float],
    gamma: float = 0.5,
) -> list[float]:
    """Mix local and remote weights: (1-gamma)*local + gamma*remote."""
    if len(local_weights) != len(remote_weights):
        raise ValueError(
            f"Dimension mismatch: local={len(local_weights)}, "
            f"remote={len(remote_weights)}"
        )
    if not (0.0 <= gamma <= 1.0):
        raise ValueError(f"gamma must be between 0.0 and 1.0, got {gamma}")

    dim = len(local_weights)
    if dim == 0:
        return []

    local_scale = 1.0 - gamma
    return [
        (local_scale * float(l_w)) + (gamma * float(r_w))
        for l_w, r_w in zip(local_weights, remote_weights)
    ]


def trimmed_mean(
    weight_vectors: Sequence[Sequence[float]],
    trim_ratio: float = 0.1,
) -> list[float]:
    """Compute coordinate-wise trimmed mean to filter out extreme outliers."""
    if not weight_vectors:
        raise ValueError("Cannot aggregate empty weight vectors")
    if not (0.0 <= trim_ratio < 0.5):
        raise ValueError(f"trim_ratio must be in [0.0, 0.5), got {trim_ratio}")

    num_vectors = len(weight_vectors)
    dim = len(weight_vectors[0])
    if dim == 0:
        return []

    for i, vec in enumerate(weight_vectors):
        if len(vec) != dim:
            raise ValueError(
                f"Dimension mismatch at index {i}: expected {dim}, got {len(vec)}"
            )

    k = int(math.floor(num_vectors * trim_ratio))
    if 2 * k >= num_vectors:
        return uniform_average(weight_vectors)

    result = [0.0] * dim
    for j in range(dim):
        coords = sorted(float(vec[j]) for vec in weight_vectors)
        trimmed = coords[k : num_vectors - k] if k > 0 else coords
        result[j] = sum(trimmed) / len(trimmed)

    return result


def euclidean_distance(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Compute Euclidean distance between two vectors."""
    if len(v1) != len(v2):
        raise ValueError("Vectors must have equal length")
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(v1, v2)))


def compute_peer_variance(weight_vectors: Sequence[Sequence[float]]) -> float:
    """Compute average mean squared distance across peer models."""
    if not weight_vectors or len(weight_vectors) < 2:
        return 0.0

    avg = uniform_average(weight_vectors)
    return sum(euclidean_distance(vec, avg) ** 2 for vec in weight_vectors) / len(
        weight_vectors
    )
