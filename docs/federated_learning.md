# Federated Learning with py-libp2p

## Overview

py-libp2p now supports decentralized federated learning through the `libp2p.federated` module. This implementation allows multiple peers to collaboratively train machine learning models without relying on a central coordinator.

## Features

### Aggregation Strategies

1. **Round-Robin Aggregation**: Different peers take turns aggregating model updates
2. **Weighted Averaging**: Aggregation weights based on peer metadata (e.g., dataset size)  
3. **Gossip Averaging**: Pairwise averaging that converges through multiple gossip rounds

### Key Components

- `DecentralizedAggregator`: Main orchestrator for federated learning
- `ModelUpdate`: Data structure for model parameter updates
- `PeerMetadata`: Information about peer capabilities and data
- `AggregationResult`: Result of aggregating multiple updates

## Verified Functionality

All three strategies have been tested and verified:
```python
# Results from test run:
# RoundRobin: 3 peers, weights mean: 2.00
# WeightedAveraging: 3 peers, weights mean: 2.22  
# GossipAveraging: 3 peers, weights mean: 2.00