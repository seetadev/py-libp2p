#!/usr/bin/env python3
"""
Simple demonstration of decentralized federated learning aggregation.
Shows multiple peers participating in federated learning with different strategies.
"""

import asyncio
import numpy as np
import logging
from multiaddr import Multiaddr

from libp2p import new_host
from libp2p.federated import (
    DecentralizedAggregator, 
    RoundRobinStrategy, 
    WeightedAveragingStrategy,
    GossipAveragingStrategy
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimplePeer:
    def __init__(self, host, aggregator, dataset_size=100):
        self.host = host
        self.aggregator = aggregator
        self.dataset_size = dataset_size
        self.model_params = self._initialize_model()
        
    def _initialize_model(self):
        """Initialize simple model parameters"""
        return {
            "weights": np.random.randn(10, 5).astype(np.float32),
            "bias": np.random.randn(5).astype(np.float32)
        }
    
    def _simulate_training(self):
        """Simulate local training by adding noise to parameters"""
        # Add small random updates to simulate training
        self.model_params["weights"] += np.random.normal(0, 0.1, self.model_params["weights"].shape)
        self.model_params["bias"] += np.random.normal(0, 0.1, self.model_params["bias"].shape)
    
    async def participate_in_round(self):
        """Participate in one round of federated learning"""
        # Simulate local training
        self._simulate_training()
        
        # Submit update to aggregator
        await self.aggregator.submit_update(self.model_params, self.dataset_size)
        
        logger.info(f"Peer {self.host.get_id()} submitted update")

async def run_aggregation_demo(strategy_name="round_robin"):
    """Run a demonstration of federated learning aggregation"""
    
    # Create strategy based on name
    if strategy_name == "round_robin":
        strategy = RoundRobinStrategy()
    elif strategy_name == "weighted":
        strategy = WeightedAveragingStrategy()
    elif strategy_name == "gossip":
        strategy = GossipAveragingStrategy()
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
    # Create multiple peers
    peers = []
    
    for i in range(3):
        # Create host
        host = new_host()
        
        # Start listening
        listen_addr = Multiaddr(f"/ip4/127.0.0.1/tcp/{9000 + i}")
        await host.get_network().listen(listen_addr)
        
        # Create aggregator
        aggregator = DecentralizedAggregator(host, strategy)
        await aggregator.start()
        
        # Create peer with different dataset sizes
        dataset_size = 100 + i * 50  # Varying dataset sizes
        peer = SimplePeer(host, aggregator, dataset_size)
        
        peers.append(peer)
        
        logger.info(f"Created peer {i} with dataset size {dataset_size}")
    
    # Connect peers to each other
    for i in range(len(peers)):
        for j in range(i + 1, len(peers)):
            peer1, peer2 = peers[i], peers[j]
            peer2_addrs = peer2.host.get_network().get_multiaddrs()
            if peer2_addrs:
                await peer1.host.connect(peer2.host.get_id(), peer2_addrs)
    
    logger.info("All peers connected")
    
    # Set up result callback for first peer
    results = []
    def result_callback(result):
        results.append(result)
        logger.info(f"Aggregation complete for round {result.round_id}")
        logger.info(f"Participating peers: {result.participating_peers}")
        logger.info(f"Strategy: {result.aggregation_strategy}")
    
    peers[0].aggregator.set_update_callback(result_callback)
    
    # Run multiple rounds
    num_rounds = 3
    for round_num in range(num_rounds):
        logger.info(f"\n--- Starting Round {round_num + 1} ---")
        
        # All peers participate in this round
        await asyncio.gather(*[peer.participate_in_round() for peer in peers])
        
        # Wait for aggregation to complete
        await asyncio.sleep(2)
        
        # Advance to next round
        for peer in peers:
            peer.aggregator.advance_round()
    
    # Print final results
    logger.info(f"\n--- Final Results ---")
    logger.info(f"Completed {len(results)} aggregation rounds")
    
    for result in results:
        logger.info(f"Round {result.round_id}: {len(result.participating_peers)} peers, strategy: {result.aggregation_strategy}")
    
    # Clean up
    for peer in peers:
        await peer.host.close()

if __name__ == "__main__":
    import sys
    strategy = sys.argv[1] if len(sys.argv) > 1 else "round_robin"
    asyncio.run(run_aggregation_demo(strategy))
