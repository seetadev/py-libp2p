"""
model.py
--------
Thin wrapper around sklearn.linear_model.LogisticRegression so the rest
of the codebase can treat "the model" as parameters (weights, bias)
rather than a scikit-learn object directly. This makes serialization
and FedAvg trivial, and keeps model.py the single place that knows
about sklearn internals.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def new_model(seed: int | None = None) -> LogisticRegression:
    """Create a fresh, untrained LogisticRegression model."""
    return LogisticRegression(max_iter=1000, random_state=seed)


def is_initialized(model: LogisticRegression) -> bool:
    return hasattr(model, "coef_")


def ensure_initialized(model: LogisticRegression, n_features: int) -> None:
    """
    sklearn's LogisticRegression has no coef_/intercept_ until fit() is
    called at least once. If we need to *inject* global parameters into
    a model that has never seen data (e.g. a brand-new peer joining
    mid-training), we fake a minimal fit so the internal shape
    bookkeeping (classes_, coef_, intercept_) exists before we
    overwrite it.
    """
    if is_initialized(model):
        return
    rng = np.random.RandomState(0)
    x_dummy = rng.randn(4, n_features)
    y_dummy = np.array([0, 1, 0, 1])
    model.fit(x_dummy, y_dummy)


def get_parameters(model: LogisticRegression) -> tuple[np.ndarray, np.ndarray]:
    """Extract (weights, bias) from a fitted model. Copies to avoid aliasing."""
    if not is_initialized(model):
        raise RuntimeError("Cannot extract parameters from an untrained model.")
    return model.coef_.copy(), model.intercept_.copy()


def set_parameters(model: LogisticRegression, weights: np.ndarray, bias: np.ndarray,
                    n_features: int) -> None:
    """Overwrite a model's parameters (e.g. with an aggregated global model)."""
    ensure_initialized(model, n_features)
    weights = np.array(weights, dtype=float)
    bias = np.array(bias, dtype=float)

    if weights.shape != model.coef_.shape:
        raise ValueError(
            f"Weight shape mismatch: model expects {model.coef_.shape}, got {weights.shape}"
        )
    if bias.shape != model.intercept_.shape:
        raise ValueError(
            f"Bias shape mismatch: model expects {model.intercept_.shape}, got {bias.shape}"
        )

    model.coef_ = weights
    model.intercept_ = bias
