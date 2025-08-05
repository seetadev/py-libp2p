# Mobile Support for py-libp2p

This directory contains the mobile compatibility layer for py-libp2p, enabling the library to run on mobile platforms like Android and iOS while maintaining compatibility with the existing desktop implementation.

## Architecture Overview

The mobile support layer provides:

1. **Runtime Adaptation**: Automatic detection and adaptation between trio (desktop) and asyncio (mobile)
2. **Mobile Transport Layer**: Asyncio-based TCP transport that coexists with the trio implementation
3. **Mobile I/O Streams**: Asyncio-compatible stream implementations
4. **Factory Pattern**: Automatic selection of appropriate implementations

## Key Components

### Runtime Adapter (`runtime.py`)
- Detects mobile runtime environments (Android, iOS, Pyodide)
- Provides unified interface for both trio and asyncio
- Includes nursery abstraction for concurrent task execution

### Mobile Transport (`transport.py`)
- `MobileTCPTransport`: Asyncio-based TCP transport implementation
- `MobileTCPListener`: Mobile-compatible TCP listener
- Full compatibility with the `ITransport` interface

### Mobile I/O (`io.py`)
- `MobileAsyncStream`: Asyncio-based stream implementation
- `MobileBufferedStream`: Buffered version for performance optimization
- Compatible with `ReadWriteCloser` interface

### Factory (`factory.py`)
- `create_tcp_transport()`: Returns appropriate transport for runtime
- `get_transport_class()`: Returns transport class for runtime

## Usage

### Basic Usage

```python
from libp2p.mobile import create_tcp_transport, is_mobile_runtime

# Check if running on mobile
if is_mobile_runtime():
    print("Running on mobile platform")

# Create appropriate transport
transport = create_tcp_transport()

# Use normally with libp2p
listener = transport.create_listener(my_handler)
```

### Manual Configuration

```python
from libp2p.mobile import AsyncRuntimeAdapter, MobileTCPTransport

# Force asyncio mode
adapter = AsyncRuntimeAdapter(force_asyncio=True)

# Create mobile transport directly
transport = MobileTCPTransport()
```

## Mobile Platform Support

### Android (Priority Platform)
- Supported via Python-for-Android (p4a)
- Uses asyncio for all async operations
- Kivy integration for UI

### iOS (Future)
- Planned support via BeeWare/Toga
- Same asyncio backend

### Progressive Web Apps
- Supported via Pyodide/WASM
- WebSocket transport planned

## Dependencies

### Mobile Requirements (`requirements-mobile.txt`)
Core dependencies for mobile platforms:
- `asyncio-compat` - Asyncio utilities
- `cryptography` - Crypto functions
- `multiaddr` - Address format
- `kivy` - Mobile UI framework
- `kivymd` - Material Design components

### Desktop Compatibility
The mobile layer coexists with existing dependencies:
- Falls back to trio when available on desktop
- Maintains full API compatibility

## Testing

### Unit Tests
```bash
# Run mobile transport tests
python test_mobile_transport.py

# Run client test
python test_mobile_transport.py client
```

### Integration Testing
1. Server test demonstrates listener functionality
2. Client test verifies connection establishment
3. Echo protocol tests bidirectional communication

## Development Guidelines

### Adding New Transports
1. Implement the `ITransport` interface
2. Use `get_runtime_adapter()` for runtime detection
3. Provide asyncio implementation with trio fallback
4. Add factory method in `factory.py`

### Platform-Specific Code
```python
from libp2p.mobile.runtime import is_mobile_runtime

if is_mobile_runtime():
    # Mobile-specific implementation
    pass
else:
    # Desktop implementation
    pass
```

### Error Handling
- Graceful degradation when trio unavailable
- Mobile-specific error handling for network issues
- Resource cleanup for mobile memory constraints

## Performance Considerations

### Mobile Optimizations
- Buffered streams for reduced system calls
- Connection pooling for battery efficiency
- Configurable timeouts for mobile networks

### Memory Management
- Explicit stream cleanup
- Bounded buffer sizes
- Garbage collection considerations

## Future Enhancements

### Planned Features
1. WebSocket transport for PWA support
2. Bluetooth transport for local mesh networking
3. Battery-aware connection management
4. Mobile-specific peer discovery mechanisms

### Platform Expansion
1. iOS support via BeeWare
2. Flutter integration via Python bridge
3. React Native support considerations

## Integration with Decentralized Chat

The mobile transport layer is designed to support the planned decentralized chat application:

1. **Peer Discovery**: Mobile-friendly discovery mechanisms
2. **Message Routing**: Efficient routing for mobile networks
3. **Offline Support**: Message queuing and sync capabilities
4. **UI Integration**: Seamless Kivy/KivyMD integration

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure mobile requirements are installed
2. **Connection Failures**: Check mobile network permissions
3. **Performance Issues**: Consider using buffered streams

### Debugging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("libp2p.mobile")
```

### Platform-Specific Issues
- Android: Ensure INTERNET permission in manifest
- iOS: Configure App Transport Security for local connections
- PWA: Handle WebSocket connection limitations

## Contributing

When contributing to mobile support:
1. Maintain compatibility with existing APIs
2. Test on actual mobile devices when possible
3. Consider battery and performance implications
4. Document platform-specific requirements
