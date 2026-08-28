"""
aggregation.py
--------------
Federated Averaging (FedAvg), weighted by each peer's num_samples:

    w_global = sum(n_k * w_k) / sum(n_k)

Every peer runs this function locally on the updates it has collected.
There is no server-side aggregator -- as long as every peer sees the
same set of updates for a round, they independently converge on the
same global model.
"""

from __future__ import annotations

import numpy as np


class AggregationError(ValueError):
    pass


def _validate_and_collect(updates: list[dict]):
    if not updates:
        raise AggregationError("Cannot aggregate an empty list of updates.")

    weights_list, bias_list, sample_counts = [], [], []
    ref_w_shape = ref_b_shape = None

    for u in updates:
        n = u["num_samples"]
        if n <= 0:
            raise AggregationError(f"Invalid num_samples={n}; must be > 0.")

        try:
            w = np.array(u["weights"], dtype=float)
            b = np.array(u["bias"], dtype=float)
        except (TypeError, ValueError) as e:
            raise AggregationError(f"Non-numeric weights/bias: {e}") from e

        if ref_w_shape is None:
            ref_w_shape, ref_b_shape = w.shape, b.shape
        elif w.shape != ref_w_shape or b.shape != ref_b_shape:
            raise AggregationError(
                f"Shape mismatch: expected weights {ref_w_shape}/bias {ref_b_shape}, "
                f"got weights {w.shape}/bias {b.shape}."
            )

        weights_list.append(w)
        bias_list.append(b)
        sample_counts.append(n)

    return weights_list, bias_list, sample_counts


def fed_avg(updates: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """
    updates: list of dicts, each with keys:
        "weights": np.ndarray-like, shape (1, n_features)
        "bias": np.ndarray-like, shape (1,)
        "num_samples": int
    Returns (global_weights, global_bias) as np.ndarray, sample-count weighted.
    """
    weights_list, bias_list, sample_counts = _validate_and_collect(updates)

    total = sum(sample_counts)
    global_weights = sum(n * w for n, w in zip(sample_counts, weights_list)) / total
    global_bias = sum(n * b for n, b in zip(sample_counts, bias_list)) / total

    return global_weights, global_bias


def simple_average(updates: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Unweighted average -- kept for tests/comparison against sample-weighted FedAvg."""
    equal_updates = [dict(u, num_samples=1) for u in updates]
    return fed_avg(equal_updates)
