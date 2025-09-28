import pytest
import asyncio
import numpy as np
from multiaddr import Multiaddr

from libp2p import new_host
from libp2p.federated import DecentralizedAggregator, RoundRobinStrategy

@pytest.mark.asyncio
async def test_multiple_peer_aggregation():
    """Test multiple peers participating in aggregation"""
    
    # Create multiple hosts
    hosts = []
    aggregators = []
    
    for i in range(3):
        host = new_host()
        listen_addr = Multiaddr(f"/ip4/127.0.0.1/tcp/{9100 + i}")
        await host.get_network().listen(listen_addr)
        
        aggregator = DecentralizedAggregator(host, RoundRobinStrategy())
        await aggregator.start()
        
        hosts.append(host)
        aggregators.append(aggregator)
    
    # Connect hosts
    for i in range(len(hosts)):
        for j in range(i + 1, len(hosts)):
            host2_addrs = hosts[j].get_network().get_multiaddrs()
            if host2_addrs:
                await hosts[i].connect(hosts[j].get_id(), host2_addrs)
    
    # Wait for connections to establish
    await asyncio.sleep(1)
    
    # Track results
    results = []
    def result_callback(result):
        results.append(result)
    
    aggregators[0].set_update_callback(result_callback)
    
    # Submit updates from all peers
    for i, aggregator in enumerate(aggregators):
        parameters = {
            "weights": np.ones((2, 2)) * (i + 1),
            "bias": np.ones(2) * (i + 1)
        }
        await aggregator.submit_update(parameters, 100 + i * 50)
    
    # Wait for aggregation
    await asyncio.sleep(2)
    
    # Verify results
    assert len(results) == 1
    result = results[0]
    assert len(result.participating_peers) == 3
    assert result.aggregation_strategy == "round_robin"
    
    # Clean up
    for host in hosts:
        await host.close()