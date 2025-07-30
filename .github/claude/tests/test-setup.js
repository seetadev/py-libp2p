import { jest } from '@jest/globals';
import 'jest-environment-node';

// Global test setup and configuration

// Mock global process methods that might be called
global.process.exit = jest.fn();
global.process.on = jest.fn();

// Setup global test timeout
jest.setTimeout(30000); // 30 seconds for async operations

// Mock common modules that are used across tests
jest.mock('fs', () => ({
  existsSync: jest.fn(),
  mkdirSync: jest.fn(),
  createWriteStream: jest.fn(() => ({
    write: jest.fn(),
    end: jest.fn()
  })),
  writeFileSync: jest.fn(),
  readFileSync: jest.fn()
}));

// Global console mock to prevent noise during testing
const originalConsole = global.console;

beforeEach(() => {
  // Reset all mocks before each test
  jest.clearAllMocks();
  
  // Mock console methods to prevent output noise
  global.console = {
    ...originalConsole,
    log: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
    info: jest.fn(),
    debug: jest.fn()
  };
});

afterEach(() => {
  // Restore console after each test
  global.console = originalConsole;
});

// Global error handler for unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Setup fake timers if needed
beforeAll(() => {
  jest.useFakeTimers();
});

afterAll(() => {
  jest.useRealTimers();
});

// Custom matchers for libp2p testing
expect.extend({
  toBeValidMultiaddr(received) {
    const pass = typeof received === 'string' && 
                  received.includes('/ip4/') && 
                  received.includes('/tcp/');
    
    if (pass) {
      return {
        message: () => `expected ${received} not to be a valid multiaddr`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${received} to be a valid multiaddr`,
        pass: false,
      };
    }
  },

  toBeValidPeerId(received) {
    const pass = typeof received === 'string' && 
                  received.length > 0 && 
                  !received.includes('/');
    
    if (pass) {
      return {
        message: () => `expected ${received} not to be a valid peer ID`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${received} to be a valid peer ID`,
        pass: false,
      };
    }
  },

  toBeValidPort(received) {
    const pass = typeof received === 'number' && 
                  Number.isInteger(received) && 
                  received >= 1024 && 
                  received <= 65535;
    
    if (pass) {
      return {
        message: () => `expected ${received} not to be a valid port`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${received} to be a valid port (1024-65535)`,
        pass: false,
      };
    }
  }
});

export default {};