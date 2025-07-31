# Stellar P2P Intents Example

A reference implementation demonstrating decentralized coordination of Stellar transactions using py-libp2p. This example allows agents to exchange signed Stellar transaction intents peer-to-peer before submitting them to the Stellar network, eliminating the need for centralized coordination infrastructure.

## Recent Fixes

This implementation has been updated to fix connection issues between regular nodes and bootstrap nodes:

- **Fixed bootstrap discovery**: Proper validation and handling of bootstrap node addresses with peer IDs
- **Improved DHT integration**: Better routing table management and peer discovery
- **Enhanced connection logic**: Robust bootstrap connection with proper error handling
- **Added address persistence**: Bootstrap nodes save their addresses for other nodes to discover
- **Fixed async patterns**: Corrected nursery usage and service lifecycle management

## Overview

This implementation enables:

- **Direct P2P communication** between Stellar agents using libp2p
- **Intent-based coordination** for payments, trustlines, and DAO votes
- **Offchain validation** before Stellar network submission  
- **Decentralized discovery** via DHT and GossipSub
- **Low-trust interactions** without custodial intermediaries

## Architecture

```
┌─────────────┐    Intent     ┌─────────────┐
│   Alice     │◄──────────────┤    Bob      │
│  (Sender)   │               │ (Receiver)  │
│             │    Response   │             │
│             ├──────────────►│             │
└─────────────┘               └─────────────┘
       │                             │
       │         libp2p P2P          │
       │        Network Layer        │
       └─────────────┬─────────────────┘
                     │
              ┌─────────────┐
              │ Bootstrap   │
              │    Node     │
              │   (DHT)     │
              └─────────────┘
                     │
              ┌─────────────┐
              │   Stellar   │
              │  Network    │
              │ (Testnet)   │
              └─────────────┘
```

## Intent Lifecycle

1. **Create Intent**: Alice creates a signed Stellar transaction intent
2. **Broadcast**: Intent is published to the P2P network via GossipSub
3. **Discover**: Bob discovers the intent through the DHT
4. **Validate**: Bob validates the intent offchain
5. **Respond**: Bob sends acceptance/rejection response
6. **Submit**: If accepted, Alice submits the transaction to Stellar

## Quick Start

### 1. Run Demo Mode (Generate Demo Accounts)

```bash
python stellar-p2p-intent.py --demo
```

This generates test Stellar keypairs and shows the exact commands to run.

### 2. Start Bootstrap Node

```bash
# Terminal 1 - Bootstrap node
python stellar-p2p-intent.py --bootstrap --port 4001
```

The bootstrap node will save its address to `stellar_bootstrap_addrs.txt` for other nodes to discover.

### 3. Start Receiver Node (Bob)

```bash
# Terminal 2 - Receiver
python stellar-p2p-intent.py 
    --secret SXXXXXXX 
    --listen 
    --port 4002
```

### 4. Send Payment Intent (Alice)

```bash
# Terminal 3 - Sender  
python stellar-p2p-intent.py 
    --secret SXXXXXXX 
    --send-to GXXXXXXX 
    --amount 10 
    --port 4003
```

## Configuration Options

### Environment Variables

```bash
# Single bootstrap address
export STELLAR_BOOTSTRAP_ADDR="/ip4/127.0.0.1/tcp/4001/p2p/12D3Koo..."

# Multiple bootstrap addresses (comma-separated)
export STELLAR_BOOTSTRAP_ADDRS="/ip4/127.0.0.1/tcp/4001/p2p/12D3Koo...,/ip4/127.0.0.1/tcp/4002/p2p/12D3Koo..."
```

### Configuration File

Create `stellar_bootstrap.json`:

```json
{
  "bootstrap_nodes": [
    "/ip4/127.0.0.1/tcp/4001/p2p/12D3Koo...",
    "/ip4/192.168.1.100/tcp/4001/p2p/12D3Koo..."
  ]
}
```

## Advanced Usage

### Send Payment Intent

```bash
python stellar-p2p-intent.py 
    --secret SXXXXXXX 
    --send-to GXXXXXXX 
    --amount 50 
    --asset XLM 
    --port 4003
```

### Listen for Intents

```bash
python stellar-p2p-intent.py 
    --secret SXXXXXXX 
    --listen 
    --port 4002
```

### Custom Bootstrap Node

**Note**: Bootstrap addresses must include peer IDs in the format `/ip4/host/tcp/port/p2p/peer_id`

```bash
python stellar-p2p-intent.py 
    --secret SXXXXXXX 
    --send-to GXXXXXXX 
    --amount 10 
    --bootstrap-addr /ip4/192.168.1.100/tcp/4001/p2p/12D3Koo...
```

## Protocol Specification

### Intent Message Format

```json
{
  "type": "intent",
  "id": "intent_abc123...",
  "intent_type": "payment",
  "from": "GXXXXXXX...",
  "to": "GYYYYYYY...",
  "amount": "10",
  "asset": "XLM",
  "transaction_xdr": "AAAAAgAAAAB...",
  "timestamp": 1234567890.123
}
```

### Response Message Format

```json
{
  "type": "response", 
  "intent_id": "intent_abc123...",
  "from": "GYYYYYYY...",
  "accepted": true,
  "timestamp": 1234567890.456
}
```

## Features

- **Multi-Asset Support**: Native XLM and custom assets
- **Auto-Funding**: Automatic testnet account funding via Friendbot
- **Intent Validation**: Comprehensive offchain validation
- **Transaction Submission**: Automatic submission after acceptance
- **DHT Discovery**: Decentralized peer discovery
- **GossipSub Messaging**: Efficient message propagation
- **Error Handling**: Robust error handling and recovery

## Network Configuration

- **Protocol**: `/stellar/intent/1.0.0`
- **Network**: Stellar Testnet
- **Horizon**: `https://horizon-testnet.stellar.org`
- **Friendbot**: `https://friendbot.stellar.org`

## Security Considerations

- All transactions are signed with Stellar keypairs
- Intents are validated before acceptance
- No private keys are transmitted over the network
- Timestamps prevent replay attacks
- XDR validation ensures transaction integrity

## Extending the Example

This example can be extended to support:

- **Multi-signature coordination**
- **Escrow negotiations** 
- **DAO voting intents**
- **DEX trading intents**
- **Cross-border payment routing**
- **Atomic swaps**

## Troubleshooting

### Common Issues

1. **Connection Failed**: Ensure bootstrap node is running first
2. **Account Not Found**: Run with `--demo` to create funded test accounts
3. **Port Conflicts**: Use different `--port` values for each node
4. **Transaction Failed**: Check account balances and network status
