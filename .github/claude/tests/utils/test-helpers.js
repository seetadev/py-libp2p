import { jest } from '@jest/globals';

/**
 * Test utilities and helpers for libp2p interop testing
 */

/**
 * Create a mock libp2p node for testing
 */
export const createMockLibp2pNode = (overrides = {}) => {
  const defaultNode = {
    peerId: {
      toString: jest.fn(() => 'mock-peer-id-12345')
    },
    start: jest.fn().mockResolvedValue(undefined),
    stop: jest.fn().mockResolvedValue(undefined),
    getMultiaddrs: jest.fn(() => [
      { toString: () => '/ip4/127.0.0.1/tcp/8000/p2p/mock-peer-id-12345' }
    ]),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dial: jest.fn().mockResolvedValue({ remotePeer: 'target-peer' }),
    services: {
      ping: jest.fn().mockResolvedValue(100),
      identify: jest.fn()
    },
    ...overrides
  };

  return defaultNode;
};

/**
 * Create mock multiaddr with specified configuration
 */
export const createMockMultiaddr = (addr, peerId = 'mock-peer-123') => ({
  getPeerId: jest.fn(() => peerId),
  toString: jest.fn(() => addr)
});

/**
 * Create mock file system operations
 */
export const createMockFs = () => ({
  existsSync: jest.fn().mockReturnValue(false),
  mkdirSync: jest.fn(),
  createWriteStream: jest.fn(() => ({
    write: jest.fn(),
    end: jest.fn()
  }))
});

/**
 * Create mock console for testing without output noise
 */
export const createMockConsole = () => {
  const originalConsole = global.console;
  
  return {
    mock: () => {
      global.console = {
        log: jest.fn(),
        error: jest.fn(),
        warn: jest.fn(),
        info: jest.fn()
      };
    },
    restore: () => {
      global.console = originalConsole;
    },
    spy: () => ({
      log: jest.spyOn(console, 'log').mockImplementation(),
      error: jest.spyOn(console, 'error').mockImplementation(),
      warn: jest.spyOn(console, 'warn').mockImplementation(),
      info: jest.spyOn(console, 'info').mockImplementation()
    })
  };
};

/**
 * Validate libp2p node configuration
 */
export const validateNodeConfig = (config) => {
  const required = ['addresses', 'transports', 'connectionEncrypters', 'streamMuxers', 'services'];
  return required.every(field => config.hasOwnProperty(field));
};

/**
 * Generate mock ping statistics
 */
export const generatePingStats = (pings) => {
  if (!pings || pings.length === 0) {
    return { min: 0, max: 0, avg: 0, sent: 0, received: 0, lost: 0 };
  }

  const validPings = pings.filter(p => typeof p === 'number' && p > 0);
  
  return {
    min: validPings.length > 0 ? Math.min(...validPings) : 0,
    max: validPings.length > 0 ? Math.max(...validPings) : 0,
    avg: validPings.length > 0 ? validPings.reduce((a, b) => a + b, 0) / validPings.length : 0,
    sent: pings.length,
    received: validPings.length,
    lost: pings.length - validPings.length
  };
};

/**
 * Validate multiaddr format
 */
export const isValidMultiaddr = (addr) => {
  if (typeof addr !== 'string') return false;
  
  const parts = addr.split('/').filter(part => part.length > 0);
  if (parts.length < 4) return false; // At minimum: ip4, address, tcp, port
  
  const hasIP = parts.includes('ip4') || parts.includes('ip6');
  const hasTCP = parts.includes('tcp');
  
  return hasIP && hasTCP;
};

/**
 * Mock event emitter for testing
 */
export class MockEventEmitter {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(event, listener) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(listener);
  }

  removeEventListener(event, listener) {
    if (this.listeners.has(event)) {
      const listeners = this.listeners.get(event);
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(listener => {
        listener({ detail: data });
      });
    }
  }

  getListeners(event) {
    return this.listeners.get(event) || [];
  }

  clearListeners(event = null) {
    if (event) {
      this.listeners.delete(event);
    } else {
      this.listeners.clear();
    }
  }
}

/**
 * Wait for a specified amount of time (for async testing)
 */
export const wait = (ms = 0) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Create a mock peer ID
 */
export const createMockPeerId = (id = null) => ({
  toString: jest.fn(() => id || `mock-peer-${Math.random().toString(36).substr(2, 9)}`)
});

/**
 * Create mock connection object
 */
export const createMockConnection = (remotePeer = 'remote-peer-123') => ({
  remotePeer,
  localPeer: 'local-peer-456',
  remoteAddr: '/ip4/127.0.0.1/tcp/8001',
  localAddr: '/ip4/127.0.0.1/tcp/8000',
  stat: {
    status: 'open',
    timeline: {
      open: Date.now()
    }
  },
  close: jest.fn().mockResolvedValue(undefined)
});

/**
 * Validate port number
 */
export const isValidPort = (port) => {
  return typeof port === 'number' && 
         Number.isInteger(port) && 
         port >= 1024 && 
         port <= 65535;
};

/**
 * Generate random port in valid range
 */
export const getRandomPort = () => {
  return Math.floor(Math.random() * (65535 - 1024 + 1)) + 1024;
};

/**
 * Mock protocol configurations
 */
export const mockProtocolConfigs = {
  ping: {
    protocolPrefix: 'ipfs',
    maxInboundStreams: 32,
    maxOutboundStreams: 64,
    timeout: 30000,
    runOnTransientConnection: true
  },
  identify: {
    protocolPrefix: 'ipfs'
  }
};

/**
 * Create timeout promise for testing async operations
 */
export const withTimeout = (promise, timeoutMs = 5000) => {
  return Promise.race([
    promise,
    new Promise((_, reject) => 
      setTimeout(() => reject(new Error(`Operation timed out after ${timeoutMs}ms`)), timeoutMs)
    )
  ]);
};

/**
 * Deep clone object for testing
 */
export const deepClone = (obj) => {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj.getTime());
  if (obj instanceof Array) return obj.map(item => deepClone(item));
  if (typeof obj === 'object') {
    const cloned = {};
    Object.keys(obj).forEach(key => {
      cloned[key] = deepClone(obj[key]);
    });
    return cloned;
  }
};

export default {
  createMockLibp2pNode,
  createMockMultiaddr,
  createMockFs,
  createMockConsole,
  validateNodeConfig,
  generatePingStats,
  isValidMultiaddr,
  MockEventEmitter,
  wait,
  createMockPeerId,
  createMockConnection,
  isValidPort,
  getRandomPort,
  mockProtocolConfigs,
  withTimeout,
  deepClone
};