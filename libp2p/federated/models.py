from dataclasses import dataclass
from typing import Dict, Any, Optional
import time
import numpy as np

@dataclass
class PeerMetadata:
    peer_id: str
    dataset_size: int
    compute_power: float = 1.0
    last_seen: float = 0.0
    
    def __post_init__(self):
        if self.last_seen == 0.0:
            self.last_seen = time.time()

@dataclass 
class ModelUpdate:
    peer_id: str
    round_id: int
    parameters: Dict[str, np.ndarray]
    metadata: PeerMetadata
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

@dataclass
class AggregationResult:
    aggregated_parameters: Dict[str, np.ndarray]
    participating_peers: list[str]
    round_id: int
    aggregation_strategy: str
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()