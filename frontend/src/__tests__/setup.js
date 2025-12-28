/**
 * Test Setup File
 *
 * This file runs before each test file. Use it to:
 * 1. Set up global mocks (APIs, browser globals)
 * 2. Configure test environment
 * 3. Add custom matchers
 *
 * Why mock these things?
 * - Tests run in Node.js, not a real browser
 * - We don't want tests to make real API calls
 * - We need to control external dependencies
 */

import { vi } from 'vitest';

// =============================================================================
// MOCK: localStorage
// =============================================================================
// Tests run in Node.js which doesn't have localStorage
// This creates a fake localStorage that stores data in memory

const localStorageMock = {
  store: {},
  getItem: vi.fn(key => localStorageMock.store[key] || null),
  setItem: vi.fn((key, value) => {
    localStorageMock.store[key] = value;
  }),
  removeItem: vi.fn(key => {
    delete localStorageMock.store[key];
  }),
  clear: vi.fn(() => {
    localStorageMock.store = {};
  }),
};

// Make it available globally (like in a real browser)
global.localStorage = localStorageMock;

// =============================================================================
// MOCK: window.location
// =============================================================================
// LoginForm reads URL query parameters (e.g., ?code=INVITE123)
// We mock this so tests can simulate different URLs

Object.defineProperty(window, 'location', {
  value: {
    search: '', // Query string like '?code=ABC123'
    href: 'http://localhost:8080',
    origin: 'http://localhost:8080',
  },
  writable: true,
});

// =============================================================================
// MOCK: fetch API
// =============================================================================
// Prevent real network requests during tests
// Individual tests will configure specific responses

global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({}),
  })
);

// =============================================================================
// MOCK: Supabase client
// =============================================================================
// The auth store imports Supabase for OAuth
// We mock it so tests don't try to connect to real Supabase

vi.mock('@/config/supabase', () => ({
  supabase: {
    auth: {
      signInWithOAuth: vi.fn(),
      getSession: vi.fn(),
      signOut: vi.fn(),
    },
  },
  getOAuthRedirectUrl: vi.fn(() => 'http://localhost:8080/auth/callback'),
}));

// =============================================================================
// MOCK: Faro (observability)
// =============================================================================
// The auth store imports Faro for metrics
// We mock it so tests don't try to send telemetry

vi.mock('@/faro', () => ({
  recordLogin: vi.fn(),
  recordLoginDuration: vi.fn(),
  recordSignup: vi.fn(),
  recordLogout: vi.fn(),
  recordSessionRefresh: vi.fn(),
  recordHttpRequest: vi.fn(),
  setFaroUser: vi.fn(),
  clearFaroUser: vi.fn(),
}));

// =============================================================================
// MOCK: API config
// =============================================================================
// Mock the API base URL so we have a consistent endpoint in tests

vi.mock('@/config/api', () => ({
  getApiBaseUrl: vi.fn(() => 'http://localhost:8000'),
}));

// =============================================================================
// MOCK: CSRF utilities
// =============================================================================

vi.mock('@/utils/csrf', () => ({
  addCSRFHeader: vi.fn(headers => headers),
  clearCSRFToken: vi.fn(),
}));

// =============================================================================
// MOCK: Trace context
// =============================================================================

vi.mock('@/utils/traceContext', () => ({
  getTraceHeaders: vi.fn(() => ({})),
}));

// =============================================================================
// Reset mocks between tests
// =============================================================================
// This runs before each test to ensure clean state

beforeEach(() => {
  // Clear localStorage between tests
  localStorageMock.store = {};
  localStorageMock.getItem.mockClear();
  localStorageMock.setItem.mockClear();
  localStorageMock.removeItem.mockClear();
  localStorageMock.clear.mockClear();

  // Reset window.location.search
  window.location.search = '';

  // Clear fetch mock
  global.fetch.mockClear();
});
