import pytest
import numpy as np
from py_libp2p.federated.aggregation import Aggregator, DecentralizedStrategies
from py_libp2p.federated.node import FederatedNode

def test_weighted_averaging():
    updates = [
        {'weights': np.array([1.0, 1.0]), 'size': 10},
        {'weights': np.array([2.0, 2.0]), 'size': 20},
    ]
    # Expected: (1*10 + 2*20) / 30 = 50 / 30 = 1.666...
    result = Aggregator.weighted_average(updates)
    assert np.allclose(result, np.array([1.66666667, 1.66666667]))

def test_round_robin_leader():
    peers = ["node_a", "node_b", "node_c"]
    # Round 0: node_a, Round 1: node_b, Round 2: node_c, Round 3: node_a
    assert DecentralizedStrategies.determine_round_robin_leader(peers, 0) == "node_a"
    assert DecentralizedStrategies.determine_round_robin_leader(peers, 1) == "node_b"
    assert DecentralizedStrategies.determine_round_robin_leader(peers, 2) == "node_c"
    assert DecentralizedStrategies.determine_round_robin_leader(peers, 3) == "node_a"

def test_gossip_averaging():
    w1 = np.array([1.0, 2.0])
    w2 = np.array([3.0, 4.0])
    result = DecentralizedStrategies.gossip_average(w1, w2)
    assert np.allclose(result, np.array([2.0, 3.0]))
