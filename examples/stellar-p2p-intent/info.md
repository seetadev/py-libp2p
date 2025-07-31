# Stellar P2P Intents Example

A reference implementation demonstrating decentralized coordination of Stellar transactions using py-libp2p. This example allows agents to exchange signed Stellar transaction intents peer-to-peer before submitting them to the Stellar network, eliminating the need for centralized coordination infrastructure.

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

### 1. Generate Demo Accounts

```bash
python main.py --demo
```

This creates test Stellar keypairs and shows the commands to run the demo.

> You may need to fund the sender's account with [Friendbot](https://lab.stellar.org/account/fund?$=network$id=testnet&label=Testnet&horizonUrl=https:////horizon-testnet.stellar.org&rpcUrl=https:////soroban-testnet.stellar.org&passphrase=Test%20SDF%20Network%20/;%20September%202015;;), if not done automatically.

### 2. Start Bootstrap Node

```bash
# Terminal 1
python main.py --bootstrap
```

### 3. Start Receiver (Bob)

```bash
# Terminal 2 - Replace SXXXXXXX with Bob's secret key
python main.py --secret SXXXXXXX --listen --port 4002
```

### 4. Send Payment Intent (Alice)

```bash
# Terminal 3 - Replace keys with Alice's secret and Bob's public key
python main.py --secret SXXXXXXX --send-to GXXXXXXX --amount 10 --port 4003
```

## Usage Examples

### Basic Payment Intent

```bash
python main.py \
    --secret SXXXXXXX \
    --send-to GXXXXXXX \
    --amount 50 \
    --asset XLM \
    --port 4003
```

### Listen for Intents

```bash
python main.py \
    --secret SXXXXXXX \
    --listen \
    --port 4002
```

### Custom Bootstrap Node

```bash
python main.py \
    --secret SXXXXXXX \
    --send-to GXXXXXXX \
    --amount 10 \
    --bootstrap-addr /ip4/192.168.1.100/tcp/4001
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
