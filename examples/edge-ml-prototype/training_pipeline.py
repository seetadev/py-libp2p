"""Simulated training pipeline with lightweight model versioning."""

from __future__ import annotations

import dataclasses
import json
import random
import time
from typing import Any


@dataclasses.dataclass
class ModelVersion:
    id: str
    name: str
    version: str
    created_at: float
    metadata: dict[str, Any]


def train_model(name: str, data_seed: int = 0) -> ModelVersion:
    """Simulate training a 'cloud' model."""
    t0 = time.time()
    random.seed(data_seed)
    accuracy = 0.8 + 0.2 * random.random()
    model_id = f"{name}-{int(t0)}"
    mv = ModelVersion(
        id=model_id,
        name=name,
        version=f"v{int(t0)}",
        created_at=t0,
        metadata={"accuracy": round(accuracy, 4), "params": 10_000},
    )
    print(
        f"[train_model] Trained {mv.name} {mv.version} acc= {mv.metadata['accuracy']}"
    )
    return mv


def serialize_model_version(mv: ModelVersion) -> str:
    return json.dumps(dataclasses.asdict(mv))
