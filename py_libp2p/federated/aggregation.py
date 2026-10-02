import numpy as np
from typing import List, Dict, Any

class Aggregator:
    """Base class for decentralized aggregation strategies."""
    @staticmethod
    def weighted_average(updates: List[Dict[str, Any]]) -> np.ndarray:
        """
        Performs weighted averaging based on metadata (e.g., dataset size).
        Each update is expected to be a dict: {'weights': np.array, 'size': int}
        """
        total_size = sum(u['size'] for u in updates)
        if total_size == 0:
            return np.zeros_like(updates[0]['weights'])
        
        weighted_sum = sum(u['weights'] * u['size'] for u in updates)
        return weighted_sum / total_size

class DecentralizedStrategies:
    """Implementation of decentralized coordination logic."""
    
    @staticmethod
    def determine_round_robin_leader(peers: List[str], round_number: int) -> str:
        """
        Determines which peer is the aggregator for the current round.
        Assumes peers list is sorted alphabetically for consistency.
        """
        sorted_peers = sorted(peers)
        index = round_number % len(sorted_peers)
        return sorted_peers[index]

    @staticmethod
    def gossip_average(local_weights: np.ndarray, remote_weights: np.ndarray) -> np.ndarray:
        """
        Simple pairwise averaging for gossip-style convergence.
        """
        return (local_weights + remote_weights) / 2.0
