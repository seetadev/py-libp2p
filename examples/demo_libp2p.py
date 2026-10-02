import asyncio
from drand_client.client import DrandClient
from drand_client.libp2p_transport import Libp2pTransport

async def main():
    print("Starting Drand Client with libp2p transport...")
    
    # Use libp2p for P2P randomness retrieval
    transport = Libp2pTransport()
    client = DrandClient(transport=transport)
    
    await client.initialize()
    
    print("Listening for randomness beacons via GossipSub...")
    try:
        async for round_data in client.listen_for_randomness():
            print(f"New Round Received: {round_data.round_number}")
            print(f"Randomness: {round_data.randomness.hex()}")
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    asyncio.run(main())
