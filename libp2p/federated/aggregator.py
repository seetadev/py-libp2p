import asyncio
import logging
from typing import Dict, List, Optional, Callable
import json

from libp2p.abc import IHost
from .models import ModelUpdate, PeerMetadata, AggregationResult
from .strategies import AggregationStrategy, RoundRobinStrategy

logger = logging.getLogger("libp2p.federated.aggregator")

class DecentralizedAggregator:
    def __init__(
        self, 
        host: IHost, 
        strategy: AggregationStrategy = None,
        aggregation_topic: str = "federated_learning_updates"
    ):
        self.host = host
        self.strategy = strategy or RoundRobinStrategy()
        self.aggregation_topic = aggregation_topic
        self.current_round = 0
        self.pending_updates: Dict[int, List[ModelUpdate]] = {}
        self.aggregation_results: Dict[int, AggregationResult] = {}
        self.peer_metadata: Dict[str, PeerMetadata] = {}
        self.update_callback: Optional[Callable[[AggregationResult], None]] = None
        
    async def start(self):
        """Initialize and start the aggregator"""
        # Subscribe to aggregation topic
        await self.host.get_pubsub().subscribe(self.aggregation_topic)
        
        # Set message handler
        self.host.get_pubsub().set_topic_validator(
            self.aggregation_topic, 
            self._handle_update_message
        )
        
        logger.info(f"Decentralized aggregator started on topic {self.aggregation_topic}")
    
    async def submit_update(self, parameters: Dict[str, "np.ndarray"], dataset_size: int):
        """Submit a model update for aggregation"""
        peer_id = str(self.host.get_id())
        
        if peer_id not in self.peer_metadata:
            self.peer_metadata[peer_id] = PeerMetadata(
                peer_id=peer_id,
                dataset_size=dataset_size
            )
        
        update = ModelUpdate(
            peer_id=peer_id,
            round_id=self.current_round,
            parameters=parameters,
            metadata=self.peer_metadata[peer_id]
        )
        
        # Serialize and publish update
        message_data = self._serialize_update(update)
        await self.host.get_pubsub().publish(self.aggregation_topic, message_data)
        
        logger.info(f"Submitted update for round {self.current_round}")
    
    async def _handle_update_message(self, message_data: bytes) -> bool:
        """Handle incoming model update messages"""
        try:
            update = self._deserialize_update(message_data)
            round_id = update.round_id
            
            # Store update
            if round_id not in self.pending_updates:
                self.pending_updates[round_id] = []
            
            self.pending_updates[round_id].append(update)
            
            # Update peer metadata
            self.peer_metadata[update.peer_id] = update.metadata
            
            logger.info(f"Received update from {update.peer_id} for round {round_id}")
            
            # Check if we have enough updates to aggregate
            await self._try_aggregate_round(round_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling update message: {e}")
            return False
    
    async def _try_aggregate_round(self, round_id: int):
        """Try to aggregate updates for a specific round"""
        if round_id not in self.pending_updates:
            return
        
        updates = self.pending_updates[round_id]
        
        # Simple condition: aggregate when we have at least 2 updates
        # In practice, you might want more sophisticated conditions
        if len(updates) >= 2:
            try:
                result = await self.strategy.aggregate(updates, round_id)
                self.aggregation_results[round_id] = result
                
                logger.info(f"Aggregated round {round_id} with {len(updates)} updates")
                
                # Clean up processed updates
                del self.pending_updates[round_id]
                
                # Notify callback if set
                if self.update_callback:
                    self.update_callback(result)
                    
            except Exception as e:
                logger.error(f"Error aggregating round {round_id}: {e}")
    
    def set_update_callback(self, callback: Callable[[AggregationResult], None]):
        """Set callback to be called when aggregation is complete"""
        self.update_callback = callback
    
    def advance_round(self):
        """Advance to the next round"""
        self.current_round += 1
        logger.info(f"Advanced to round {self.current_round}")
    
    def get_latest_result(self) -> Optional[AggregationResult]:
        """Get the latest aggregation result"""
        if not self.aggregation_results:
            return None
        latest_round = max(self.aggregation_results.keys())
        return self.aggregation_results[latest_round]
    
    def _serialize_update(self, update: ModelUpdate) -> bytes:
        """Serialize model update for transmission"""
        # Simple JSON serialization (in practice, you'd use more efficient serialization)
        data = {
            "peer_id": update.peer_id,
            "round_id": update.round_id,
            "parameters": {k: v.tolist() for k, v in update.parameters.items()},
            "metadata": {
                "peer_id": update.metadata.peer_id,
                "dataset_size": update.metadata.dataset_size,
                "compute_power": update.metadata.compute_power,
                "last_seen": update.metadata.last_seen
            },
            "timestamp": update.timestamp
        }
        return json.dumps(data).encode()
    
    def _deserialize_update(self, data: bytes) -> ModelUpdate:
        """Deserialize model update from transmission"""
        import numpy as np
        
        obj = json.loads(data.decode())
        
        parameters = {k: np.array(v) for k, v in obj["parameters"].items()}
        metadata = PeerMetadata(**obj["metadata"])
        
        return ModelUpdate(
            peer_id=obj["peer_id"],
            round_id=obj["round_id"],
            parameters=parameters,
            metadata=metadata,
            timestamp=obj["timestamp"]
        )
