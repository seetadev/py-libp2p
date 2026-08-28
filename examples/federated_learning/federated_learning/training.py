"""
training.py
------------
Local training + evaluation. X_local / y_local live only in memory
inside whatever calls these functions -- they are never passed to
serialization.py or protocol.py, and never cross the network.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from . import model as model_lib


def train_local_model(model: LogisticRegression, X_train: np.ndarray, y_train: np.ndarray) -> LogisticRegression:
    model.fit(X_train, y_train)
    return model


def evaluate(model: LogisticRegression, X_test: np.ndarray, y_test: np.ndarray) -> float:
    if not model_lib.is_initialized(model):
        raise RuntimeError("Cannot evaluate an untrained model.")
    return float(model.score(X_test, y_test))


def local_round(model: LogisticRegression, X_train, y_train, X_test, y_test):
    """Train + evaluate + extract parameters in one call. Returns (weights, bias, accuracy)."""
    train_local_model(model, X_train, y_train)
    acc = evaluate(model, X_test, y_test)
    weights, bias = model_lib.get_parameters(model)
    return weights, bias, acc
