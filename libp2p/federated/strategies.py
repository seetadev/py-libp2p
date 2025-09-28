from abc import ABC, abstractmethod
from typing import List, Dict
import numpy as np
import random
import logging

from .models import ModelUpdate, AggregationResult

logger = logging.getLogger("libp2p.federated.strategies")

class AggregationStrategy(ABC):
    @abstractmethod
    async def aggregate(self, updates: List[ModelUpdate], round_id: int) -> AggregationResult:
        pass

class RoundRobinStrategy(AggregationStrategy):
    def __init__(self):
        self.current_aggregator_index = 0
        self.peer_list = []
    
    async def aggregate(self, updates: List[ModelUpdate], round_id: int) -> AggregationResult:
        if not updates:
            raise ValueError("No updates to aggregate")
        
        # Update peer list based on participating peers
        participating_peers = [update.peer_id for update in updates]
        self.peer_list = list(set(self.peer_list + participating_peers))
        
        # Select aggregator for this round
        aggregator_peer = self.peer_list[self.current_aggregator_index % len(self.peer_list)]
        self.current_aggregator_index += 1
        
        logger.info(f"Round {round_id}: Peer {aggregator_peer} is aggregating")
        
        # Simple averaging aggregation
        aggregated_params = self._average_parameters(updates)
        
        return AggregationResult(
            aggregated_parameters=aggregated_params,
            participating_peers=participating_peers,
            round_id=round_id,
            aggregation_strategy="round_robin"
        )
    
    def _average_parameters(self, updates: List[ModelUpdate]) -> Dict[str, np.ndarray]:
        if not updates:
            return {}
        
        # Get parameter keys from first update
        param_keys = updates[0].parameters.keys()
        aggregated = {}
        
        for key in param_keys:
            # Stack all parameters for this key
            params = [update.parameters[key] for update in updates]
            # Simple average
            aggregated[key] = np.mean(params, axis=0)
        
        return aggregated

class WeightedAveragingStrategy(AggregationStrategy):
    async def aggregate(self, updates: List[ModelUpdate], round_id: int) -> AggregationResult:
        if not updates:
            raise ValueError("No updates to aggregate")
        
        participating_peers = [update.peer_id for update in updates]
        
        # Calculate weights based on dataset sizes
        total_data_size = sum(update.metadata.dataset_size for update in updates)
        weights = [update.metadata.dataset_size / total_data_size for update in updates]
        
        logger.info(f"Round {round_id}: Weighted aggregation with weights {weights}")
        
        # Weighted averaging
        aggregated_params = self._weighted_average_parameters(updates, weights)
        
        return AggregationResult(
            aggregated_parameters=aggregated_params,
            participating_peers=participating_peers,
            round_id=round_id,
            aggregation_strategy="weighted_averaging"
        )
    
    def _weighted_average_parameters(self, updates: List[ModelUpdate], weights: List[float]) -> Dict[str, np.ndarray]:
        if not updates:
            return {}
        
        param_keys = updates[0].parameters.keys()
        aggregated = {}
        
        for key in param_keys:
            weighted_sum = None
            for update, weight in zip(updates, weights):
                param = update.parameters[key] * weight
                if weighted_sum is None:
                    weighted_sum = param
                else:
                    weighted_sum += param
            aggregated[key] = weighted_sum
        
        return aggregated

class GossipAveragingStrategy(AggregationStrategy):
    def __init__(self, gossip_rounds: int = 3):
        self.gossip_rounds = gossip_rounds
    
    async def aggregate(self, updates: List[ModelUpdate], round_id: int) -> AggregationResult:
        if not updates:
            raise ValueError("No updates to aggregate")
        
        participating_peers = [update.peer_id for update in updates]
        
        logger.info(f"Round {round_id}: Gossip aggregation with {self.gossip_rounds} gossip rounds")
        
        # Simulate gossip-style pairwise averaging
        current_params = [update.parameters for update in updates]
        
        for gossip_round in range(self.gossip_rounds):
            current_params = self._gossip_round(current_params)
        
        # Final aggregated result
        aggregated_params = self._average_parameter_dicts(current_params)
        
        return AggregationResult(
            aggregated_parameters=aggregated_params,
            participating_peers=participating_peers,
            round_id=round_id,
            aggregation_strategy="gossip_averaging"
        )
    
    def _gossip_round(self, param_dicts: List[Dict[str, np.ndarray]]) -> List[Dict[str, np.ndarray]]:
        """Simulate one round of gossip where pairs of peers average their parameters"""
        n_peers = len(param_dicts)
        if n_peers < 2:
            return param_dicts
        
        # Create pairs randomly
        indices = list(range(n_peers))
        random.shuffle(indices)
        
        new_params = param_dicts.copy()
        
        # Average parameters between pairs
        for i in range(0, len(indices) - 1, 2):
            idx1, idx2 = indices[i], indices[i + 1]
            averaged = self._average_two_parameter_dicts(param_dicts[idx1], param_dicts[idx2])
            new_params[idx1] = averaged
            new_params[idx2] = averaged
        
        return new_params
    
    def _average_two_parameter_dicts(self, params1: Dict[str, np.ndarray], params2: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        averaged = {}
        for key in params1.keys():
            averaged[key] = (params1[key] + params2[key]) / 2
        return averaged
    
    def _average_parameter_dicts(self, param_dicts: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
        if not param_dicts:
            return {}
        
        param_keys = param_dicts[0].keys()
        aggregated = {}
        
        for key in param_keys:
            params = [param_dict[key] for param_dict in param_dicts]
            aggregated[key] = np.mean(params, axis=0)
        
        return aggregated