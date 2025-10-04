"""Simulate deployment of an EdgeModel to a node"""

from __future__ import annotations

import time
from typing import Any

from model_distiller import EdgeModel


class Deployment:
    def __init__(self, model: EdgeModel, node_id: str):
        self.model = model
        self.node_id = node_id
        self.deployed_at = time.time()
        self.status = "deployed"

    def into(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "model_id": self.model.id,
            "model_version": self.model.version,
            "status": self.status,
            "deployed_at": self.deployed_at,
        }


def deploy_to_node(edge_model: EdgeModel, node_id: str) -> Deployment:
    # Simulate a samll delay
    print(f"[deploy_to_node] Deploying {edge_model.name} to {node_id} ...")
    time.sleep(0.1)
    d = Deployment(edge_model, node_id)
    print(f"[deploy_to_node] Deployed {edge_model.name} to {node_id}")
    return d
