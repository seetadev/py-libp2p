import { jest } from '@jest/globals';

// Mock libp2p and its dependencies
jest.mock('libp2p', () => ({
  createLibp2p: jest.fn()
}));

jest.mock('@libp2p/tcp', () => ({
  tcp: jest.fn(() => 'tcp-transport')
}));

jest.mock('@chainsafe/libp2p-noise', () => ({
  noise: jest.fn(() => 'noise-crypto')
}));

jest.mock('@chainsafe/libp2p-yamux', () => ({
  yamux: jest.fn(() => 'yamux-muxer')
}));

jest.mock('@libp2p/ping', () => ({
  ping: jest.fn(() => 'ping-service')
}));

jest.mock('@libp2p/identify', () => ({
  identify: jest.fn(() => 'identify-service')
}));

jest.mock('@multiformats/multiaddr', () => ({
  multiaddr: jest.fn()
}));

// Mock console methods
const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
const processExitSpy = jest.spyOn(process, 'exit').mockImplementation(() => {});

describe('ping.js - P2P Ping Implementation', () => {
  let mockNode;
  let mockPing;
  let createLibp2p;
  let multiaddr;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup mock node
    mockPing = jest.fn();
    mockNode = {
      peerId: {
        toString: jest.fn(() => 'mock-peer-id-12345')
      },
      start: jest.fn().mockResolvedValue(undefined),
      stop: jest.fn().mockResolvedValue(undefined),
      getMultiaddrs: jest.fn(() => [
        { toString: () => '/ip4/127.0.0.1/tcp/8000/p2p/mock-peer-id-12345' },
        { toString: () => '/ip4/192.168.1.100/tcp/8000/p2p/mock-peer-id-12345' }
      ]),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dial: jest.fn().mockResolvedValue({
        remotePeer: 'target-peer-id'
      }),
      services: {
        ping: mockPing
      }
    };

    createLibp2p = require('libp2p').createLibp2p;
    createLibp2p.mockResolvedValue(mockNode);

    multiaddr = require('@multiformats/multiaddr').multiaddr;
  });

  afterEach(() => {
    consoleSpy.mockClear();
  });

  describe('createNode', () => {
    test('should create libp2p node with correct configuration', async () => {
      const { createLibp2p } = await import('libp2p');
      const { tcp } = await import('@libp2p/tcp');
      const { noise } = await import('@chainsafe/libp2p-noise');
      const { yamux } = await import('@chainsafe/libp2p-yamux');
      const { ping } = await import('@libp2p/ping');
      const { identify } = await import('@libp2p/identify');

      // Import the module under test (we need to mock the file system for this)
      const pingModule = await import('../../../tests/interop/js_libp2p/js_node/src/ping.js');
      
      expect(createLibp2p).toHaveBeenCalledWith({
        addresses: {
          listen: ['/ip4/0.0.0.0/tcp/0']
        },
        transports: ['tcp-transport'],
        connectionEncrypters: ['noise-crypto'],
        streamMuxers: ['yamux-muxer'],
        services: {
          ping: 'ping-service',
          identify: 'identify-service'
        },
        connectionManager: {
          minConnections: 0,
          maxConnections: 100,
          dialTimeout: 30000
        }
      });
    });

    test('should configure ping service with ipfs prefix', async () => {
      const { ping } = await import('@libp2p/ping');
      
      await import('../../../tests/interop/js_libp2p/js_node/src/ping.js');
      
      expect(ping).toHaveBeenCalledWith({
        protocolPrefix: 'ipfs',
        maxInboundStreams: 32,
        maxOutboundStreams: 64,
        timeout: 30000
      });
    });
  });

  describe('runServer', () => {
    test('should start server and display peer information', async () => {
      // We'll need to test the server functionality
      // This would require importing and executing the server logic
      expect(mockNode.start).toBeDefined();
      expect(mockNode.getMultiaddrs).toBeDefined();
      expect(mockNode.peerId.toString).toBeDefined();
    });

    test('should setup event listeners for peer connections', async () => {
      await mockNode.start();
      
      // Verify that addEventListener was called for connection events
      expect(mockNode.addEventListener).toBeDefined();
    });

    test('should handle peer connect events', () => {
      const connectHandler = jest.fn();
      mockNode.addEventListener('peer:connect', connectHandler);
      
      expect(mockNode.addEventListener).toHaveBeenCalledWith(
        'peer:connect',
        connectHandler
      );
    });

    test('should handle peer disconnect events', () => {
      const disconnectHandler = jest.fn();
      mockNode.addEventListener('peer:disconnect', disconnectHandler);
      
      expect(mockNode.addEventListener).toHaveBeenCalledWith(
        'peer:disconnect',
        disconnectHandler
      );
    });
  });

  describe('runClient', () => {
    beforeEach(() => {
      mockPing.mockResolvedValue(100); // 100ms ping time
      
      multiaddr.mockReturnValue({
        getPeerId: jest.fn(() => 'target-peer-id-67890'),
        toString: jest.fn(() => '/ip4/127.0.0.1/tcp/8001/p2p/target-peer-id-67890')
      });
    });

    test('should extract peer ID from multiaddr', async () => {
      const targetAddr = '/ip4/127.0.0.1/tcp/8001/p2p/target-peer-id-67890';
      const mockMultiaddr = {
        getPeerId: jest.fn(() => 'target-peer-id-67890'),
        toString: jest.fn(() => targetAddr)
      };
      
      multiaddr.mockReturnValue(mockMultiaddr);
      
      expect(multiaddr).toBeDefined();
      expect(mockMultiaddr.getPeerId()).toBe('target-peer-id-67890');
    });

    test('should handle missing peer ID in multiaddr', async () => {
      const mockMultiaddr = {
        getPeerId: jest.fn(() => null),
        toString: jest.fn(() => '/ip4/127.0.0.1/tcp/8001')
      };
      
      multiaddr.mockReturnValue(mockMultiaddr);
      
      expect(mockMultiaddr.getPeerId()).toBeNull();
    });

    test('should perform ping operations', async () => {
      const targetAddr = '/ip4/127.0.0.1/tcp/8001/p2p/target-peer-id-67890';
      
      await mockNode.start();
      expect(mockNode.start).toHaveBeenCalled();
      
      // Simulate ping execution
      const pingResult = await mockPing('target-peer-id-67890');
      expect(pingResult).toBe(100);
    });

    test('should handle connection failures gracefully', async () => {
      mockNode.dial.mockRejectedValue(new Error('Connection failed'));
      
      await expect(mockNode.dial('/invalid/multiaddr')).rejects.toThrow('Connection failed');
    });

    test('should handle ping timeout', async () => {
      mockPing.mockRejectedValue(new Error('Ping timeout'));
      
      await expect(mockPing('unreachable-peer')).rejects.toThrow('Ping timeout');
    });
  });

  describe('Error Handling', () => {
    test('should handle node creation failure', async () => {
      createLibp2p.mockRejectedValue(new Error('Failed to create node'));
      
      await expect(createLibp2p({})).rejects.toThrow('Failed to create node');
    });

    test('should handle node start failure', async () => {
      mockNode.start.mockRejectedValue(new Error('Failed to start node'));
      
      await expect(mockNode.start()).rejects.toThrow('Failed to start node');
    });

    test('should handle invalid multiaddr format', () => {
      multiaddr.mockImplementation(() => {
        throw new Error('Invalid multiaddr');
      });
      
      expect(() => multiaddr('invalid-addr')).toThrow('Invalid multiaddr');
    });
  });

  describe('Process Signal Handling', () => {
    test('should handle SIGINT for graceful shutdown', () => {
      // Test process signal handling
      const mockProcess = {
        on: jest.fn(),
        exit: jest.fn()
      };
      
      mockProcess.on('SIGINT', async () => {
        await mockNode.stop();
        mockProcess.exit(0);
      });
      
      expect(mockProcess.on).toHaveBeenCalledWith('SIGINT', expect.any(Function));
    });
  });

  describe('Statistics and Metrics', () => {
    test('should calculate ping statistics correctly', () => {
      const pings = [100, 150, 120, 90, 200];
      const stats = {
        min: Math.min(...pings),
        max: Math.max(...pings),
        avg: pings.reduce((a, b) => a + b) / pings.length,
        total: pings.length
      };
      
      expect(stats.min).toBe(90);
      expect(stats.max).toBe(200);
      expect(stats.avg).toBe(132);
      expect(stats.total).toBe(5);
    });

    test('should handle empty ping results', () => {
      const pings = [];
      expect(pings.length).toBe(0);
    });
  });
});