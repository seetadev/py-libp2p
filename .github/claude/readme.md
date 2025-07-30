# py-libp2p

<h1 align="center">
  <a href="https://libp2p.io/"><img width="250" src="https://github.com/libp2p/py-libp2p/blob/main/assets/py-libp2p-logo.png?raw=true" alt="py-libp2p hex logo" /></a>
</h1>

<h3 align="center">The Python implementation of the libp2p networking stack.</h3>

[![Discord](https://img.shields.io/discord/1204447718093750272?color=blueviolet&label=discord)](https://discord.gg/hQJnbd85N6)
[![PyPI version](https://badge.fury.io/py/libp2p.svg)](https://badge.fury.io/py/libp2p)
[![Python versions](https://img.shields.io/pypi/pyversions/libp2p.svg)](https://pypi.python.org/pypi/libp2p)
[![Build Status](https://img.shields.io/github/actions/workflow/status/libp2p/py-libp2p/tox.yml?branch=main&label=build%20status)](https://github.com/libp2p/py-libp2p/actions/workflows/tox.yml)
[![Docs build](https://readthedocs.org/projects/py-libp2p/badge/?version=latest)](http://py-libp2p.readthedocs.io/en/latest/?badge=latest)

py-libp2p is a comprehensive Python implementation of the libp2p modular networking stack. It provides a robust foundation for building decentralized applications with peer-to-peer networking capabilities, offering secure communication, stream multiplexing, and peer discovery mechanisms.

## 🚀 Features

### Core Networking
- **Multi-transport Support**: TCP transport with experimental QUIC and WebSocket support
- **Stream Multiplexing**: Mplex and Yamux stream multiplexers for efficient connection management
- **Security Protocols**: Noise, SECIO, and insecure protocols for encrypted communications
- **Protocol Multiplexing**: Advanced protocol negotiation and routing capabilities

### Peer Discovery & NAT Traversal
- **mDNS Discovery**: Automatic local peer discovery using multicast DNS
- **Kademlia DHT**: Distributed hash table for peer routing and content discovery
- **Circuit Relay v2**: Advanced relay mechanisms for NAT traversal
- **AutoNAT**: Automatic network address translation detection
- **Identify Protocol**: Peer identification and capability advertisement

### Communication Patterns
- **Publish-Subscribe (PubSub)**: Efficient message broadcasting with various routing algorithms
- **Direct Messaging**: Point-to-point communication between peers
- **Protocol Handlers**: Custom protocol implementation support

### Cryptography & Security
- **Multiple Key Types**: RSA, Ed25519, ECDSA, and secp256k1 support
- **X25519 Key Exchange**: Elliptic curve Diffie-Hellman key agreement
- **Authenticated Encryption**: ChaCha20-Poly1305 and AES-GCM support
- **Digital Signatures**: Comprehensive signing and verification capabilities

## 🛠️ Tech Stack

### Core Technologies
- **Python 3.8+**: Modern Python with asyncio support
- **Protocol Buffers**: Efficient serialization for network protocols
- **Cryptography Libraries**: Industry-standard cryptographic implementations

### Development Tools
- **Tox**: Testing across multiple Python versions
- **Sphinx**: Comprehensive documentation generation
- **Makefile**: Build automation and development workflows
- **GitHub Actions**: Continuous integration and deployment
- **Codecov**: Code coverage analysis

### Dependencies
- **Multiaddr**: Network address abstraction
- **Multistream-select**: Protocol negotiation
- **Async/await**: Modern asynchronous programming patterns

## 📁 Project Structure

```
py-libp2p/
├── libp2p/                    # Core library implementation
│   ├── crypto/                # Cryptographic primitives and protocols
│   ├── discovery/             # Peer discovery mechanisms (mDNS, events)
│   ├── host/                  # Host implementation and AutoNAT
│   ├── identity/              # Identity and identification protocols
│   ├── kad_dht/               # Kademlia distributed hash table
│   ├── network/               # Network layer and connection management
│   ├── peer/                  # Peer management and addressing
│   ├── pubsub/                # Publish-subscribe messaging
│   ├── relay/                 # Circuit relay v2 implementation
│   ├── security/              # Security protocols (Noise, SECIO)
│   ├── stream_muxer/          # Stream multiplexing (Mplex, Yamux)
│   ├── transport/             # Transport layer implementations
│   └── utils/                 # Utility functions and helpers
├── examples/                  # Comprehensive usage examples
│   ├── chat/                  # P2P chat application
│   ├── echo/                  # Echo server/client example
│   ├── ping/                  # Network ping implementation
│   └── pubsub/                # Publish-subscribe examples
├── tests/                     # Comprehensive test suite
├── docs/                      # Sphinx documentation
└── scripts/                   # Development and release scripts
```

## 🔧 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git (for development)

### Installation Steps

#### From PyPI (Recommended)
```bash
pip install libp2p
```

#### From Source (Development)
```bash
# Clone the repository
git clone https://github.com/anisharma07/py-libp2p.git
cd py-libp2p

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e .
pip install -r requirements-dev.txt
```

## 🎯 Usage

### Basic Host Creation
```python
import asyncio
from libp2p import new_host

async def main():
    # Create a new libp2p host
    host = new_host()
    
    # Start the host
    await host.start()
    
    print(f"Host ID: {host.get_id()}")
    print(f"Host addresses: {host.get_addrs()}")
    
    # Keep the host running
    await asyncio.sleep(60)
    
    # Clean shutdown
    await host.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Echo Protocol Example
```bash
# Terminal 1 - Start echo server
cd examples/echo
python echo.py server

# Terminal 2 - Connect as client
python echo.py client /ip4/127.0.0.1/tcp/8000
```

### Chat Application
```bash
# Start interactive P2P chat
cd examples/chat
python chat.py
```

### Publish-Subscribe Messaging
```bash
# Start pubsub example
cd examples/pubsub
python pubsub.py
```

### Development Mode
```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Build documentation
make docs

# Run linting
make lint

# Run type checking
make type-check
```

## 📱 Platform Support

- **Linux**: Full support (primary development platform)
- **macOS**: Full support
- **Windows**: Full support with Windows-specific adaptations
- **Docker**: Container support for deployment
- **Cloud Platforms**: Compatible with major cloud providers

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=libp2p --cov-report=html

# Run specific test categories
python -m pytest tests/core/          # Core functionality
python -m pytest tests/discovery/    # Discovery mechanisms
python -m pytest tests/interop/      # Interoperability tests
```

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Cross-component interaction testing
- **Interoperability Tests**: Compatibility with other libp2p implementations
- **Performance Tests**: Benchmarking and performance validation

## 🔄 Deployment

### Production Deployment
```bash
# Install production dependencies only
pip install libp2p --no-dev

# Set production environment variables
export LIBP2P_LOG_LEVEL=INFO
export LIBP2P_METRICS_ENABLED=true
```

### Docker Deployment
```bash
# Build Docker image
docker build -t py-libp2p-app .

# Run container
docker run -p 8000:8000 py-libp2p-app
```

### Configuration
```python
# Advanced host configuration
from libp2p import new_host
from libp2p.security import NoiseSecurityTransport
from libp2p.stream_muxer import MplexStreamMuxer

host = new_host(
    security_transports=[NoiseSecurityTransport()],
    stream_muxers=[MplexStreamMuxer()],
    listen_addrs=["/ip4/0.0.0.0/tcp/8000"]
)
```

## 📊 Performance & Optimization

### Performance Features
- **Async/Await**: Non-blocking I/O for high concurrency
- **Connection Pooling**: Efficient connection reuse
- **Stream Multiplexing**: Multiple logical streams over single connections
- **Protocol Negotiation Caching**: Reduced handshake overhead

### Monitoring & Metrics
```python
# Enable built-in metrics
from libp2p.tools import MetricsCollector

metrics = MetricsCollector()
host = new_host(metrics=metrics)

# Access performance metrics
print(f"Active connections: {metrics.active_connections}")
print(f"Messages sent: {metrics.messages_sent}")
```

## 🤝 Contributing

We welcome contributions! This project is maintained by [@pacrob](https://github.com/pacrob), [@seetadev](https://github.com/seetadev), and [@dhuseby](https://github.com/dhuseby), and we're looking for assistance!

### Getting Started
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following our coding standards
4. Add tests for new functionality
5. Run the test suite and ensure all tests pass
6. Commit your changes (`git commit -m 'Add some amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Guidelines
- **Code Style**: Follow PEP 8 and use Black for formatting
- **Type Hints**: Use comprehensive type annotations
- **Documentation**: Update docstrings and documentation for new features
- **Testing**: Maintain test coverage above 80%
- **Commits**: Use conventional commit messages

### Issue Templates
- **Bug Reports**: Use the bug report template for issues
- **Feature Requests**: Use the feature request template for new ideas
- **Enhancements**: Use the enhancement template for improvements

## 📄 License

This project is dual-licensed under:
- **MIT License** - See [LICENSE-MIT](LICENSE-MIT) for details
- **Apache License 2.0** - See [LICENSE-APACHE](LICENSE-APACHE) for details

You may choose either license for your use of this software.

## 🙏 Acknowledgments

- **libp2p Community**: For the excellent specifications and reference implementations
- **Protocol Labs**: For pioneering the libp2p networking stack
- **Python Community**: For the robust ecosystem and async/await support
- **Contributors**: All developers who have contributed to this implementation

### Related Projects
- [go-libp2p](https://github.com/libp2p/go-libp2p) - Go implementation
- [rust-libp2p](https://github.com/libp2p/rust-libp2p) - Rust implementation
- [js-libp2p](https://github.com/libp2p/js-libp2p) - JavaScript implementation

## 📞 Support & Contact

- **Documentation**: [py-libp2p.readthedocs.io](https://py-libp2p.readthedocs.io/)
- **Discord Community**: [Join our Discord](https://discord.gg/hQJnbd85N6)
- **GitHub Discussions**: [Technical Questions](https://github.com/libp2p/py-libp2p/discussions/new?category=q-a)
- **Community Forum**: [discuss.libp2p.io](https://discuss.libp2p.io)
- **Issue Tracker**: [GitHub Issues](https://github.com/anisharma07/py-libp2p/issues)

### Quick Links
- 📖 [Read the Documentation](https://py-libp2p.readthedocs.io/en/latest/)
- 🔄 [Release Notes](https://py-libp2p.readthedocs.io/en/latest/release_notes.html)
- 🎯 [Examples Directory](./examples/)
- 🧪 [Run Tests](./tests/)

---

*Built with ❤️ by the libp2p community. Join us in building the decentralized web!*