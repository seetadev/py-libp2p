import pytest
import numpy as np

from libp2p.federated.strategies import (
    RoundRobinStrategy, 
    WeightedAveragingStrategy, 
    GossipAveragingStrategy
)
from libp2p.federated.models import ModelUpdate, PeerMetadata

@pytest.fixture
def sample_updates():
    """Create sample model updates for testing"""
    updates = []
    for i in range(3):
        metadata = PeerMetadata(
            peer_id=f"peer_{i}",
            dataset_size=100 + i * 50
        )
        
        parameters = {
            "weights": np.ones((2, 2)) * (i + 1),
            "bias": np.ones(2) * (i + 1)
        }
        
        update = ModelUpdate(
            peer_id=f"peer_{i}",
            round_id=1,
            parameters=parameters,
            metadata=metadata
        )
        updates.append(update)
    
    return updates

@pytest.mark.asyncio
async def test_round_robin_strategy(sample_updates):
    """Test round-robin aggregation strategy"""
    strategy = RoundRobinStrategy()
    
    result = await strategy.aggregate(sample_updates, 1)
    
    assert result.round_id == 1
    assert result.aggregation_strategy == "round_robin"
    assert len(result.participating_peers) == 3
    
    # Check that averaging worked correctly
    expected_weights = np.ones((2, 2)) * 2  # (1+2+3)/3 = 2
    expected_bias = np.ones(2) * 2
    
    np.testing.assert_array_almost_equal(
        result.aggregated_parameters["weights"], 
        expected_weights
    )
    np.testing.assert_array_almost_equal(
        result.aggregated_parameters["bias"], 
        expected_bias
    )

@pytest.mark.asyncio
async def test_weighted_averaging_strategy(sample_updates):
    """Test weighted averaging strategy"""
    strategy = WeightedAveragingStrategy()
    
    result = await strategy.aggregate(sample_updates, 1)
    
    assert result.aggregation_strategy == "weighted_averaging"

@pytest.mark.asyncio
async def test_empty_updates():
    """Test that strategies handle empty update lists gracefully"""
    strategy = RoundRobinStrategy()
    
    with pytest.raises(ValueError, match="No updates to aggregate"):
        await strategy.aggregate([], 1)
