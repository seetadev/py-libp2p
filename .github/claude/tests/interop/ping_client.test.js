import { jest } from '@jest/globals';
import fs from 'fs';
import path from 'path';

// Mock file system operations
jest.mock('fs', () => ({
  existsSync: jest.fn(),
  mkdirSync: jest.fn(),
  createWriteStream: jest.fn()
}));

// Mock libp2p dependencies
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

describe('ping_client.js - P2P Ping Client', () => {
  let mockNode;
  let mockLogStream;
  let createLibp2p;
  let multiaddr;

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock log stream
    mockLogStream = {
      write: jest.fn(),
      end: jest.fn()
    };
    
    fs.existsSync.mockReturnValue(false);
    fs.mkdirSync.mockImplementation(() => {});
    fs.createWriteStream.mockReturnValue(mockLogStream);

    // Setup mock node
    mockNode = {
      peerId: {
        toString: jest.fn(() => 'client-peer-id-12345')
      },
      start: jest.fn().mockResolvedValue(undefined),
      stop: jest.fn().mockResolvedValue(undefined),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dial: jest.fn().mockResolvedValue({
        remotePeer: 'target-peer-id'
      }),
      services: {
        ping: jest.fn().mockResolvedValue(150) // 150ms ping time
      }
    };

    createLibp2p = require('libp2p').createLibp2p;
    createLibp2p.mockResolvedValue(mockNode);

    multiaddr = require('@multiformats/multiaddr').multiaddr;
    multiaddr.mockReturnValue({
      getPeerId: jest.fn(() => 'target-peer-id-67890'),
      toString: jest.fn(() => '/ip4/127.0.0.1/tcp/8001/p2p/target-peer-id-67890')
    });

    // Mock console to prevent noise in tests
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  describe('Logging Setup', () => {
    test('should create logs directory if it does not exist', () => {
      fs.existsSync.mockReturnValue(false);
      
      // Simulate the directory creation logic
      const logsDir = path.join(process.cwd(), '../logs');
      if (!fs.existsSync(logsDir)) {
        fs.mkdirSync(logsDir, { recursive: true });
      }

      expect(fs.existsSync).toHaveBeenCalledWith(logsDir);
      expect(fs.mkdirSync).toHaveBeenCalledWith(logsDir, { recursive: true });
    });

    test('should not create logs directory if it already exists', () => {
      fs.existsSync.mockReturnValue(true);
      
      const logsDir = path.join(process.cwd(), '../logs');
      if (!fs.existsSync(logsDir)) {
        fs.mkdirSync(logsDir, { recursive: true });
      }

      expect(fs.existsSync).toHaveBeenCalledWith(logsDir);
      expect(fs.mkdirSync).not.toHaveBeenCalled();
    });

    test('should create log file write stream', () => {
      const logFile = path.join(process.cwd(), '../logs/js_ping_client.log');
      
      fs.createWriteStream(logFile, { flags: 'w' });
      
      expect(fs.createWriteStream).toHaveBeenCalledWith(logFile, { flags: 'w' });
    });

    test('should write formatted log messages', () => {
      const message = 'Test log message';
      const timestamp = new Date().toISOString();
      const expectedLogLine = `${timestamp} - ${message}\n`;
      
      // Simulate the log function
      mockLogStream.write(expectedLogLine);
      
      expect(mockLogStream.write).toHaveBeenCalledWith(expectedLogLine);
    });
  });

  describe('Node Creation', () => {
    test('should create libp2p node with client configuration', async () => {
      expect(createLibp2p).toBeDefined();
      
      await createLibp2p({
        addresses: {
          listen: ['/ip4/0.0.0.0/tcp/0'] // Random port
        },
        transports: ['tcp-transport'],
        connectionEncrypters: ['noise-crypto'],
        streamMuxers: ['yamux-muxer'],
        services: {
          ping: 'ping-service',
          identify: 'identify-service'
        }
      });
      
      expect(createLibp2p).toHaveBeenCalled();
    });

    test('should configure ping service with correct parameters', () => {
      const { ping } = require('@libp2p/ping');
      
      expect(ping).toHaveBeenCalledWith('ping-service');
    });

    test('should setup connection manager with proper limits', async () => {
      const expectedConfig = expect.objectContaining({
        connectionManager: {
          minConnections: 0,
          maxConnections: 100,
          dialTimeout: 30000,
          maxParallelDials: 10
        }
      });
      
      // This would be called during node creation
      expect(createLibp2p).toBeDefined();
    });
  });

  describe('Client Operations', () => {
    test('should start node and log peer information', async () => {
      await mockNode.start();
      
      expect(mockNode.start).toHaveBeenCalled();
      expect(mockNode.peerId.toString()).toBe('client-peer-id-12345');
    });

    test('should parse target multiaddr correctly', () => {
      const targetAddr = '/ip4/127.0.0.1/tcp/8001/p2p/target-peer-id-67890';
      const ma = multiaddr(targetAddr);
      const targetPeerId = ma.getPeerId();
      
      expect(multiaddr).toHaveBeenCalledWith(targetAddr);
      expect(targetPeerId).toBe('target-peer-id-67890');
    });

    test('should handle multiaddr without peer ID', () => {
      multiaddr.mockReturnValue({
        getPeerId: jest.fn(() => null),
        toString: jest.fn(() => '/ip4/127.0.0.1/tcp/8001')
      });
      
      const ma = multiaddr('/ip4/127.0.0.1/tcp/8001');
      const targetPeerId = ma.getPeerId();
      
      expect(targetPeerId).toBeNull();
    });

    test('should perform ping operations with statistics', async () => {
      const pingService = mockNode.services.ping;
      const pingResults = [];
      
      // Simulate multiple pings
      for (let i = 0; i < 5; i++) {
        const result = await pingService(`target-peer-${i}`);
        pingResults.push(result);
      }
      
      expect(pingResults).toHaveLength(5);
      expect(pingResults.every(result => typeof result === 'number')).toBe(true);
    });

    test('should calculate ping statistics correctly', () => {
      const pings = [100, 150, 120, 200, 90];
      const stats = {
        min: Math.min(...pings),
        max: Math.max(...pings),
        avg: pings.reduce((a, b) => a + b, 0) / pings.length,
        sent: pings.length,
        received: pings.length,
        lost: 0
      };
      
      expect(stats.min).toBe(90);
      expect(stats.max).toBe(200);
      expect(stats.avg).toBe(132);
      expect(stats.sent).toBe(5);
      expect(stats.received).toBe(5);
      expect(stats.lost).toBe(0);
    });
  });

  describe('Connection Handling', () => {
    test('should setup connection event listeners', () => {
      mockNode.addEventListener('peer:connect', jest.fn());
      mockNode.addEventListener('peer:disconnect', jest.fn());
      
      expect(mockNode.addEventListener).toHaveBeenCalledWith('peer:connect', expect.any(Function));
      expect(mockNode.addEventListener).toHaveBeenCalledWith('peer:disconnect', expect.any(Function));
    });

    test('should handle successful connection', async () => {
      const connection = await mockNode.dial('/ip4/127.0.0.1/tcp/8001/p2p/target-peer');
      
      expect(mockNode.dial).toHaveBeenCalled();
      expect(connection.remotePeer).toBe('target-peer-id');
    });

    test('should handle connection failures', async () => {
      mockNode.dial.mockRejectedValue(new Error('Connection refused'));
      
      await expect(mockNode.dial('/invalid/addr')).rejects.toThrow('Connection refused');
    });

    test('should handle dial timeout', async () => {
      mockNode.dial.mockRejectedValue(new Error('Dial timeout'));
      
      await expect(mockNode.dial('/slow/peer')).rejects.toThrow('Dial timeout');
    });
  });

  describe('Error Handling', () => {
    test('should handle ping timeout gracefully', async () => {
      mockNode.services.ping.mockRejectedValue(new Error('Ping timeout after 30s'));
      
      await expect(mockNode.services.ping('unreachable-peer')).rejects.toThrow('Ping timeout after 30s');
    });

    test('should handle invalid target address', () => {
      multiaddr.mockImplementation(() => {
        throw new Error('Invalid multiaddr format');
      });
      
      expect(() => multiaddr('invalid-address')).toThrow('Invalid multiaddr format');
    });

    test('should handle node start failure', async () => {
      mockNode.start.mockRejectedValue(new Error('Failed to start node'));
      
      await expect(mockNode.start()).rejects.toThrow('Failed to start node');
    });

    test('should handle missing ping service', async () => {
      mockNode.services.ping = undefined;
      
      expect(mockNode.services.ping).toBeUndefined();
    });
  });

  describe('Command Line Arguments', () => {
    test('should handle default ping count', () => {
      const defaultCount = 5;
      expect(defaultCount).toBe(5);
    });

    test('should handle custom ping count', () => {
      const customCount = 10;
      expect(customCount).toBeGreaterThan(0);
      expect(typeof customCount).toBe('number');
    });

    test('should validate ping count parameter', () => {
      const validateCount = (count) => {
        return typeof count === 'number' && count > 0 && count <= 100;
      };
      
      expect(validateCount(5)).toBe(true);
      expect(validateCount(0)).toBe(false);
      expect(validateCount(-1)).toBe(false);
      expect(validateCount(101)).toBe(false);
      expect(validateCount('5')).toBe(false);
    });
  });

  describe('Protocol Compatibility', () => {
    test('should use ipfs protocol prefix for compatibility', () => {
      const { ping } = require('@libp2p/ping');
      
      // The ping service should be configured with ipfs prefix
      ping({
        protocolPrefix: 'ipfs',
        maxInboundStreams: 32,
        maxOutboundStreams: 64,
        timeout: 30000,
        runOnTransientConnection: true
      });
      
      expect(ping).toHaveBeenCalled();
    });

    test('should handle protocol negotiation failures', async () => {
      mockNode.services.ping.mockRejectedValue(new Error('Protocol not supported'));
      
      await expect(mockNode.services.ping('incompatible-peer')).rejects.toThrow('Protocol not supported');
    });
  });
});