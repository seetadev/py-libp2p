"""
Simulate model distillation: produce a smaller edge model 
from cloud model metadata.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Any

from training_pipeline import ModelVersion


@dataclasses.dataclass
class EdgeModel:
    id: str
    name: str
    version: str
    created_at: float
    metadata: dict[str, Any]


def distill_model(
    cloud_model: ModelVersion, compression_ratio: float = 0.1
) -> EdgeModel:
    """Simulate distillation: smaller params, slightly lower accuracy"""
    t0 = time.time()
    acc = max(0.5, cloud_model.metadat.get("accuracy", 0.7) - 0.05)
    params = int(cloud_model.metadata.get("params", 1000) * compression_ratio)
    mid = f"{cloud_model.id}-distilled"
    em = EdgeModel(
        id=mid,
        name=cloud_model.name + "-edge",
        version=f"{cloud_model.version}-d",
        created_at=t0,
        metadata={"accuracy": round(acc, 4), "params": params},
    )

    print(
        f"[distill_model] Distilled {cloud_model.name}->{em.name}"
        f"acc= {em.metadata['accuracy']} params={em.metadata['params']}"
    )
    return em
