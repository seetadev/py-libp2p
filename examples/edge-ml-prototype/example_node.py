"""
Example CLI to run a 'cloud' node(trainer) or an edge node(deploy+ monitor).
This shows how libp2p would be used to announce deployments/model meta via p2p.
"""

from __future__ import annotations

import argparse
import asyncio
import random

from deployment_manager import deploy_to_node
from drift_detector import SimpleDriftDetector
from model_distiller import distill_model
from performance_monitor import check_and_alert, simulate_inference
from training_pipeline import serialize_model_version, train_model


async def run_cloud(name: str):
    m = train_model(name, data_seed=random.randint(0, 1000))
    payload = serialize_model_version(m)
    print(f"[cloud] would publish model metadata over libp2p: {payload}")
    e = distill_model(m)
    print(f"[cloud] Would publish distilled edge model metadata: {e}")


async def run_edge(node_id: str, baseline_seed: int = 42):
    baseline = [random.uniform(0.1, 0.3) for _ in range(50 + baseline_seed % 10)]
    drift_detector = SimpleDriftDetector(baseline_data=baseline, threshold=0.25)
    print(f"[edge:{node_id}] Simulating receiving edge model metadata ...")

    # Simuate deploy
    # create an artificial edge model placeholder
    class EM:
        pass

    em = EM()
    em.id = f"edge-model-{node_id}"
    em.name = "example-edge"
    em.version = "v1-d"
    deployed = deploy_to_node(em, node_id)
    # monitor loop
    for i in range(5):
        metric = simulate_inference(
            deployed.model.id if hasattr(deployed.model, "id") else deployed.model_id
        )
        check_and_alert(metric, latency_threshold=120.0)
        new_data = [random.uniform(0.1, 0.3 if i < 3 else 0.6) for _ in range(20)]
        drift_info = drift_detector.detect_drift(new_data)
        if drift_info.get("drift"):
            print(f"[edge:{node_id}] Data drift detected: {drift_info}")
        await asyncio.sleep(0.2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["cloud", "edge"], required=True)
    parser.add_argument("--node-id", default="edge-1")
    parser.add_argument("--baseline-seed", type=int, default=42)
    args = parser.parse_args()
    if args.role == "cloud":
        asyncio.run(run_cloud(args.name))
    else:
        asyncio.run(run_edge(args.node_id, baseline_seed=args.baseline_seed))


if __name__ == "__main__":
    main()
