````markdown
**starknet-p2p-intents**
A reference implementation of intent-based coordination for Starknet dApps using `py-libp2p`. Enables decentralized offchain exchange of signed transaction intents between peers.

**Features**
- P2P messaging with `py-libp2p`
- GossipSub pubsub over `/starknet/intent/1.0.0`
- Signed Starknet intents using `starknet.py`
- JSON-based message encoding and verification
- CLI interface for running a bootstrap and peer node

**Installation**
```bash
python3 -m venv venv
source venv/bin/activate
cd libp2p/starknet_intents
````

Demo
**Run Bootstrap Node**

```bash
python cli.py bootstrap
```

Copy the printed `/ip4/.../p2p/...` address.

**Run Peer Node**

```bash
python cli.py peer --bootstrap-addr "<MULTIADDR>"
```

Example:

```bash
python cli.py peer --bootstrap-addr "/ip4/127.0.0.1/tcp/9000/p2p/QmXYZ..."
```

**Intent Format**

Example intent structure:

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
  "chain_id": "SN_GOERLI"
}
```

**Architecture**

- Nodes communicate via libp2p GossipSub
- Each peer sends a signed JSON intent
- Bootstrap node receives and logs intents
  \`
