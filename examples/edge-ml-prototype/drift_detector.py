"""A tiny, toy drift detector: compares running mean of a sensor to baseline."""

from collections.abc import Sequence
import statistics
from typing import Any


class SimpleDriftDetector:
    def __init__(self, baseline_data: Sequence[float], threshold: float = 0.2):
        self.baseline_mean = statistics.mean(baseline_data) if baseline_data else 0.0
        self.threshold = threshold

    def check(self, new_data: Sequence[float]) -> dict[str, Any]:
        if not new_data:
            return {"drift": False}
        m = statistics.mean(new_data)
        diff = abs(m - self.baseline_mean) / (abs(self.baseline_mean) + 1e-9)
        drift = diff > self.threshold
        return {
            "drift": drift,
            "baseline_mean": self.baseline_mean,
            "new_mean": m,
            "diff": diff,
        }
