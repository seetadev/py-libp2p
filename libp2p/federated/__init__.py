"""
Decentralized Federated Learning and Aggregation module for py-libp2p.
"""

from libp2p.federated.payload import ModelPayload
from libp2p.federated.aggregation import (
    uniform_average,
    weighted_average,
    pairwise_mix,
    trimmed_mean,
    euclidean_distance,
    compute_peer_variance,
)
from libp2p.federated.gossip import GossipAggregator
from libp2p.federated.round_robin import RoundRobinAggregator

__all__ = [
    "ModelPayload",
    "uniform_average",
    "weighted_average",
    "pairwise_mix",
    "trimmed_mean",
    "euclidean_distance",
    "compute_peer_variance",
    "GossipAggregator",
    "RoundRobinAggregator",
]
