"""
Simple monitoring: measure simulated inference latency and 
raise alert if > threshold.
"""

import random
from typing import Any


def simulate_inference(edge_model_id: str) -> dict[str, Any]:
    # Simuate variable inference latency
    latency_ms = random.uniform(5, 200)
    accuracy = random.uniform(0.5, 0.95)
    metric = {
        "model_id": edge_model_id,
        "latency_ms": latency_ms,
        "accuracy": round(accuracy, 3),
    }
    return metric


def check_and_alert(metric: dict[str, Any], latency_threshold: float = 100.0):
    if metric["latency_ms"] > latency_threshold:
        print(
            f"[Alert] High latency {metric['latency_ms']:.1f} ms"
            f"for model {metric['model_id']}"
        )
    else:
        print(
            f"[monitor] OK latency {metric['latency_ms']:.1f}msfor {metric['model_id']}"
        )
