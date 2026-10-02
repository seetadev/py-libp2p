import asyncio
import numpy as np
from py_libp2p.federated.aggregation import Aggregator, DecentralizedStrategies

class FederatedNode:
    def __init__(self, peer_id, host, port, dataset_size=100):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.dataset_size = dataset_size
        self.model_weights = np.random.rand(10)  # Simulated model weights
        self.peers = set()
        self.current_round = 0

    async def send_update(self, target_peer, transport):
        """Sends local weights and metadata to a specific peer."""
        payload = {
            'sender': self.peer_id,
            'weights': self.model_weights,
            'size': self.dataset_size,
            'round': self.current_round
        }
        await transport.send(target_peer, payload)

    def handle_update(self, update: dict):
        """Processes a received update."""
        # In a real scenario, this would be stored in a buffer until the round ends
        return update

    async def run_round_robin_step(self, transport):
        """Executes one round of Round-Robin aggregation."""
        all_peers = list(self.peers) + [self.peer_id]
        leader = DecentralizedStrategies.determine_round_robin_leader(all_peers, self.current_round)
        
        if self.peer_id == leader:
            print(f"Node {self.peer_id} is the leader for round {self.current_round}")
            # In a real implementation, the leader would wait for updates from all peers
            # Here we simulate the aggregation of collected updates
            updates = [] # This would be populated by handle_update
            # Simulation: assume we got updates from 2 other peers
            updates.append({'weights': np.random.rand(10), 'size': 100})
            updates.append({'weights': np.random.rand(10), 'size': 200})
            updates.append({'weights': self.model_weights, 'size': self.dataset_size})
            
            self.model_weights = Aggregator.weighted_average(updates)
            print(f"Node {self.peer_id} aggregated weights for round {self.current_round}")
        else:
            print(f"Node {self.peer_id} sending update to leader {leader}")
            await self.send_update(leader, transport)
        
        self.current_round += 1

    async def run_gossip_step(self, target_peer, transport):
        """Executes one step of Gossip averaging."""
        # Send weights to a random peer and receive theirs
        await self.send_update(target_peer, transport)
        # Simulate receiving weights from target_peer
        remote_weights = np.random.rand(10) 
        self.model_weights = DecentralizedStrategies.gossip_average(self.model_weights, remote_weights)
        print(f"Node {self.peer_id} performed gossip averaging with {target_peer}")
