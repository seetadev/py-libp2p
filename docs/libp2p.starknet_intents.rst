 ## Installation
````markdown

```bash
cd libp2p/starknet_intents
python3 -m venv venv
source venv/bin/activate
````

> Make sure to export a test private key:

```bash
export STARKNET_PRIVATE_KEY=0xabc123...
```

## CLI Usage

### Bootstrap Node

```bash
python cli.py bootstrap
```

Copy the printed `/ip4/.../p2p/...` address.

### Peer Node

```bash
python cli.py peer --bootstrap-addr "/ip4/127.0.0.1/tcp/9000/p2p/QmXYZ..."
```

### Generate Intent (includes metadata)

```bash
python cli.py generate-intent \
  --sender 0x0489...e5 \
  --contract 0x072d...e6 \
  --calldata 1 2 1000000000000000000 \
  --nonce 1 \
  --token-from 0xStarknetTokenAddress \
  --token-to 0xEthereumTokenAddress \
  --amount 1000000000000000000
```

### Send Intent via P2P

```bash
python cli.py send-intent \
  --bootstrap-addr "/ip4/127.0.0.1/tcp/9000/p2p/QmXYZ..."
```

### Run a Resolver Node

```bash
python resolver.py "/ip4/127.0.0.1/tcp/9000/p2p/QmXYZ..."
```

## Intent Format

```json
{
  "from": "0xSender",
  "to": "0xContract",
  "calldata": [1, 2],
  "nonce": 123456,
  "signature": {
    "r": "...",
    "s": "..."
  },
  "chain_id": "SN_GOERLI",
  "intent_metadata": {
    "type": "cross_chain_swap",
    "hashlock": "...",
    "timelock": 1754220000,
    "created_at": 1754216400,
    "token_from": "0xStarknetTokenAddress",
    "token_to": "0xEthereumTokenAddress",
    "amount": 1000000000000000000
  }
}
```

## Architecture

* Nodes communicate over `libp2p` using `GossipSub` on topic `/starknet/intent/1.0.0`
* Peers sign and broadcast Starknet transaction intents
* Resolvers receive and process matching intents, enabling Fusion swaps coordination


## NPM Dependencies (for resolver scripts)

```bash
npm install @1inch/fusion-sdk@2 \
            libp2p @libp2p/tcp \
            @libp2p/identify @chainsafe/libp2p-noise \
            @chainsafe/libp2p-yamux @chainsafe/libp2p-gossipsub \
            @libp2p/pubsub-peer-discovery
```
