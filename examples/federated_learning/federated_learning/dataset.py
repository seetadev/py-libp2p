"""
dataset.py
----------
Generates a synthetic classification dataset and splits it across
peers with *different* class distributions per peer (non-IID), so
aggregation actually demonstrates value: no single peer sees a
representative sample of the full data on its own.

Peer 0 -> biased toward class 0
Peer 1 -> biased toward class 1
Peer 2+ -> mixed / roughly balanced

The full dataset (X, y) is generated once from a fixed seed so that
every peer process, run independently, derives the *same* global
dataset before shredding it into local shards -- this is a simulation
convenience only. In a real deployment each peer would simply load
its own private data from disk.
"""

from __future__ import annotations

import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split


def generate_global_dataset(n_samples: int = 900, n_features: int = 10, seed: int = 42):
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=max(2, n_features // 2),
        n_redundant=min(2, n_features // 4),
        n_classes=2,
        random_state=seed,
    )
    return X, y


def _bias_split(X: np.ndarray, y: np.ndarray, target_class: int, purity: float,
                 n_samples: int, rng: np.random.RandomState):
    """Pick n_samples biased toward target_class at the given purity ratio."""
    idx_target = np.where(y == target_class)[0]
    idx_other = np.where(y != target_class)[0]

    n_target = min(int(n_samples * purity), len(idx_target))
    n_other = min(n_samples - n_target, len(idx_other))

    chosen = np.concatenate([
        rng.choice(idx_target, n_target, replace=False),
        rng.choice(idx_other, n_other, replace=False),
    ])
    rng.shuffle(chosen)
    return X[chosen], y[chosen]


def split_for_peers(X: np.ndarray, y: np.ndarray, n_peers: int, seed: int = 42):
    """Split the dataset into n_peers non-IID shards."""
    if n_peers < 1:
        raise ValueError("n_peers must be >= 1")

    rng = np.random.RandomState(seed)
    per_peer = len(X) // n_peers
    shards = []

    for i in range(n_peers):
        if i == 0:
            shard = _bias_split(X, y, target_class=0, purity=0.85, n_samples=per_peer, rng=rng)
        elif i == 1:
            shard = _bias_split(X, y, target_class=1, purity=0.85, n_samples=per_peer, rng=rng)
        else:
            shard = _bias_split(X, y, target_class=i % 2, purity=0.55, n_samples=per_peer, rng=rng)
        shards.append(shard)

    return shards


def load_local_dataset(peer_index: int, n_peers: int, n_samples: int = 900,
                        n_features: int = 10, seed: int = 42, test_size: float = 0.2):
    """
    Convenience entry point used by run_peer.py: returns
    (X_train, X_test, y_train, y_test) for a single peer's local shard.
    """
    if not (0 <= peer_index < n_peers):
        raise ValueError(f"peer_index must be in [0, {n_peers}), got {peer_index}")

    X, y = generate_global_dataset(n_samples=n_samples, n_features=n_features, seed=seed)
    shards = split_for_peers(X, y, n_peers, seed=seed)
    X_local, y_local = shards[peer_index]

    # Guard against a shard that's too small/imbalanced to stratify safely.
    stratify = y_local if len(np.unique(y_local)) > 1 and len(y_local) >= 10 else None
    return train_test_split(X_local, y_local, test_size=test_size, random_state=seed, stratify=stratify)
