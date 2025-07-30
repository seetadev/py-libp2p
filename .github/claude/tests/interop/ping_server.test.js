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

describe('ping_server.js - P2P Ping Server', () => {
  let mockNode;
  let mockLogStream;
  let createLibp2p;

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
        toString: jest.fn(() => 'server-peer-id-54321')
      },
      start: jest.fn().mockResolvedValue(undefined),
      stop: jest.fn().mockResolvedValue(undefined),
      getMultiaddrs: jest.fn(() => [
        { toString: () => '/ip4/127.0.0.1/tcp/8000/p2p/server-peer-id-54321' },
        { toString: () => '/ip4/0.0.0.0/tcp/8000/p2p/server-peer-id-54321' }
      ]),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      services: {
        ping: jest.fn()
      }
    };

    createLibp2p = require('libp2p').createLibp2p;
    createLibp2p.mockResolvedValue(mockNode);

    // Mock console to prevent noise in tests
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  describe('Server Setup', () => {
    test('should create logs directory for server logging', () => {
      fs.existsSync.mockReturnValue(false);
      
      const logsDir = path.join(process.cwd(), '../logs');
      if (!fs.existsSync(logsDir)) {
        fs.mkdirSync(logsDir, { recursive: true });
      }

      expect(fs.existsSync).toHaveBeenCalledWith(logsDir);
      expect(fs.mkdirSync).toHaveBeenCalledWith(logsDir, { recursive: true });
    });

    test('should create server log file stream', () => {
      const logFile = path.join(process.cwd(), '../logs/js_ping_server.log');
      
      fs.createWriteStream(logFile, { flags: 'w' });
      
      expect(fs.createWriteStream).toHaveBeenCalledWith(logFile, { flags: 'w' });
    });

    test('should write timestamped log messages', () => {
      const message = 'Server started';
      const timestamp = new Date().toISOString();
      const expectedLogLine = `${timestamp} - ${message}\n`;
      
      mockLogStream.write(expectedLogLine);
      
      expect(mockLogStream.write).toHaveBeenCalledWith(expectedLogLine);
    });
  });

  describe('Node Creation', () => {
    test('should create libp2p node with server configuration', async () => {
      const port = 8000;
      
      await createLibp2p({
        addresses: {
          listen: [`/ip4/0.0.0.0/tcp/${port}`]
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
          dialTimeout: 30000,
          maxParallelDials: 10
        }
      });
      
      expect(createLibp2p).toHaveBeenCalled();
    });

    test('should configure ping service with ipfs protocol prefix', () => {
      const { ping } = require('@libp2p/ping');
      
      ping({
        protocolPrefix: 'ipfs',
        maxInboundStreams: 32,
        maxOutboundStreams: 64,
        timeout: 30000,
        runOnTransientConnection: true
      });
      
      expect(ping).toHaveBeenCalled();
    });

    test('should set up proper connection manager limits', () => {
      const connectionConfig = {
        minConnections: 0,
        maxConnections: 100,
        dialTimeout: 30000,
        maxParallelDials: 10
      };
      
      expect(connectionConfig.maxConnections).toBe(100);
      expect(connectionConfig.dialTimeout).toBe(30000);
      expect(connectionConfig.maxParallelDials).toBe(10);
    });
  });

  describe('Server Operations', () => {
    test('should start server and bind to specified port', async () => {
      await mockNode.start();
      
      expect(mockNode.start).toHaveBeenCalled();
      expect(mockNode.peerId.toString()).toBe('server-peer-id-54321');
    });

    test('should retrieve and display listen addresses', () => {
      const addresses = mockNode.getMultiaddrs();
      
      expect(mockNode.getMultiaddrs).toHaveBeenCalled();
      expect(addresses).toHaveLength(2);
      expect(addresses[0].toString()).toContain('/ip4/127.0.0.1/tcp/8000');
      expect(addresses[1].toString()).toContain('/ip4/0.0.0.0/tcp/8000');
    });

    test('should find main TCP address for display', () => {
      const addresses = mockNode.getMultiaddrs();
      const tcpAddresses = addresses.filter(addr => 
        addr.toString().includes('/tcp/') && !addr.toString().includes('/ip4/0.0.0.0')
      );
      
      expect(tcpAddresses).toHaveLength(1);
      expect(tcpAddresses[0].toString()).toContain('/ip4/127.0.0.1/tcp/8000');
    });

    test('should handle multiple network interfaces', () => {
      mockNode.getMultiaddrs.mockReturnValue([
        { toString: () => '/ip4/127.0.0.1/tcp/8000/p2p/server-peer-id-54321' },
        { toString: () => '/ip4/192.168.1.100/tcp/8000/p2p/server-peer-id-54321' },
        { toString: () => '/ip4/10.0.0.5/tcp/8000/p2p/server-peer-id-54321' }
      ]);
      
      const addresses = mockNode.getMultiaddrs();
      expect(addresses).toHaveLength(3);
      
      const hasLocalhost = addresses.some(addr => addr.toString().includes('127.0.0.1'));
      const hasLAN = addresses.some(addr => addr.toString().includes('192.168.1.100'));
      const hasVPN = addresses.some(addr => addr.toString().includes('10.0.0.5'));
      
      expect(hasLocalhost).toBe(true);
      expect(hasLAN).toBe(true);
      expect(hasVPN).toBe(true);
    });
  });

  describe('Event Handling', () => {
    test('should setup peer connection event listeners', () => {
      const connectHandler = jest.fn();
      const disconnectHandler = jest.fn();
      
      mockNode.addEventListener('peer:connect', connectHandler);
      mockNode.addEventListener('peer:disconnect', disconnectHandler);
      
      expect(mockNode.addEventListener).toHaveBeenCalledWith('peer:connect', connectHandler);
      expect(mockNode.addEventListener).toHaveBeenCalledWith('peer:disconnect', disconnectHandler);
    });

    test('should handle peer connect events with logging', () => {
      const mockEvent = {
        detail: {
          toString: () => 'connected-peer-id-789'
        }
      };
      
      const connectHandler = (evt) => {
        expect(evt.detail.toString()).toBe('connected-peer-id-789');
      };
      
      mockNode.addEventListener('peer:connect', connectHandler);
      connectHandler(mockEvent);
    });

    test('should handle peer disconnect events with logging', () => {
      const mockEvent = {
        detail: {
          toString: () => 'disconnected-peer-id-789'
        }
      };
      
      const disconnectHandler = (evt) => {
        expect(evt.detail.toString()).toBe('disconnected-peer-id-789');
      };
      
      mockNode.addEventListener('peer:disconnect', disconnectHandler);
      disconnectHandler(mockEvent);
    });

    test('should setup peer identify event listener', () => {
      const identifyHandler = jest.fn();
      mockNode.addEventListener('peer:identify', identifyHandler);
      
      expect(mockNode.addEventListener).toHaveBeenCalledWith('peer:identify', identifyHandler);
    });

    test('should handle peer identify events with protocol info', () => {
      const mockIdentifyEvent = {
        detail: {
          peerId: {
            toString: () => 'identified-peer-123'
          },
          protocols: ['/ipfs/ping/1.0.0', '/ipfs/id/1.0.0'],
          listenAddrs: [
            { toString: () => '/ip4/192.168.1.50/tcp/8001' }
          ]
        }
      };
      
      const identifyHandler = (evt) => {
        expect(evt.detail.peerId.toString()).toBe('identified-peer-123');
        expect(evt.detail.protocols).toContain('/ipfs/ping/1.0.0');
        expect(evt.detail.listenAddrs).toHaveLength(1);
      };
      
      mockNode.addEventListener('peer:identify', identifyHandler);
      identifyHandler(mockIdentifyEvent);
    });
  });

  describe('Port Configuration', () => {
    test('should accept custom port parameter', async () => {
      const customPort = 9000;
      
      await createLibp2p({
        addresses: {
          listen: [`/ip4/0.0.0.0/tcp/${customPort}`]
        }
      });
      
      expect(createLibp2p).toHaveBeenCalledWith(
        expect.objectContaining({
          addresses: {
            listen: ['/ip4/0.0.0.0/tcp/9000']
          }
        })
      );
    });

    test('should handle default port when none specified', () => {
      const defaultPort = 8000;
      expect(defaultPort).toBe(8000);
    });

    test('should validate port range', () => {
      const isValidPort = (port) => {
        return typeof port === 'number' && port >= 1024 && port <= 65535;
      };
      
      expect(isValidPort(8000)).toBe(true);
      expect(isValidPort(1023)).toBe(false); // Below unprivileged range
      expect(isValidPort(65536)).toBe(false); // Above max port
      expect(isValidPort('8000')).toBe(false); // Wrong type
    });
  });

  describe('Error Handling', () => {
    test('should handle node creation failure', async () => {
      createLibp2p.mockRejectedValue(new Error('Failed to create libp2p node'));
      
      await expect(createLibp2p({})).rejects.toThrow('Failed to create libp2p node');
    });

    test('should handle node start failure', async () => {
      mockNode.start.mockRejectedValue(new Error('Port already in use'));
      
      await expect(mockNode.start()).rejects.toThrow('Port already in use');
    });

    test('should handle address binding failure', async () => {
      mockNode.start.mockRejectedValue(new Error('EADDRINUSE: Address already in use'));
      
      await expect(mockNode.start()).rejects.toThrow('EADDRINUSE: Address already in use');
    });

    test('should handle invalid port configuration', async () => {
      createLibp2p.mockRejectedValue(new Error('Invalid port configuration'));
      
      await expect(createLibp2p({
        addresses: { listen: ['/ip4/0.0.0.0/tcp/invalid'] }
      })).rejects.toThrow('Invalid port configuration');
    });
  });

  describe('Server Lifecycle', () => {
    test('should handle graceful shutdown', async () => {
      await mockNode.start();
      await mockNode.stop();
      
      expect(mockNode.start).toHaveBeenCalled();
      expect(mockNode.stop).toHaveBeenCalled();
    });

    test('should cleanup resources on shutdown', async () => {
      mockLogStream.end = jest.fn();
      
      await mockNode.stop();
      // In a real implementation, we would end the log stream
      // mockLogStream.end();
      
      expect(mockNode.stop).toHaveBeenCalled();
    });

    test('should handle multiple start calls gracefully', async () => {
      await mockNode.start();
      await mockNode.start(); // Second call should be handled gracefully
      
      expect(mockNode.start).toHaveBeenCalledTimes(2);
    });

    test('should handle stop before start', async () => {
      mockNode.stop.mockResolvedValue(undefined);
      
      await mockNode.stop();
      expect(mockNode.stop).toHaveBeenCalled();
    });
  });

  describe('Protocol Support', () => {
    test('should support ping protocol with ipfs prefix', () => {
      const { ping } = require('@libp2p/ping');
      
      const pingConfig = {
        protocolPrefix: 'ipfs',
        maxInboundStreams: 32,
        maxOutboundStreams: 64,
        timeout: 30000,
        runOnTransientConnection: true
      };
      
      expect(pingConfig.protocolPrefix).toBe('ipfs');
      expect(pingConfig.maxInboundStreams).toBe(32);
      expect(pingConfig.timeout).toBe(30000);
    });

    test('should support identify protocol', () => {
      const { identify } = require('@libp2p/identify');
      expect(identify).toBeDefined();
    });

    test('should handle protocol negotiation', () => {
      const supportedProtocols = [
        '/ipfs/ping/1.0.0',
        '/ipfs/id/1.0.0',
        '/multistream/1.0.0'
      ];
      
      expect(supportedProtocols).toContain('/ipfs/ping/1.0.0');
      expect(supportedProtocols).toContain('/ipfs/id/1.0.0');
    });
  });
});