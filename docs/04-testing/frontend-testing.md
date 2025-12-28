# Frontend Testing Guide

**Last Updated:** December 28, 2025

---

## Overview

The frontend uses **Vitest** with **Vue Test Utils** for component testing. Tests run in a simulated browser environment using **happy-dom**.

### Quick Start

```bash
cd frontend

# Run tests once
npm run test:run

# Run tests in watch mode (re-runs on file changes)
npm test

# Run with coverage report
npm run test:coverage
```

---

## Test Infrastructure

### Dependencies

| Package | Purpose |
|---------|---------|
| `vitest` | Test framework (made by Vite team) |
| `@vue/test-utils` | Vue component mounting and interaction |
| `happy-dom` | Fast DOM simulation for Node.js |

### File Structure

```
frontend/
├── vitest.config.js              # Test configuration
├── src/
│   └── __tests__/
│       ├── setup.js              # Global mocks and test setup
│       └── components/
│           └── LoginForm.spec.js # Component tests
```

### Configuration Files

**vitest.config.js** - Main test configuration:
- Uses `happy-dom` for DOM simulation
- Enables global test APIs (`describe`, `it`, `expect`)
- Configures `@` path alias
- Sets up coverage reporting

**src/__tests__/setup.js** - Runs before each test:
- Mocks `localStorage` (not available in Node.js)
- Mocks `window.location` for URL parameters
- Mocks `fetch` to prevent real API calls
- Mocks external modules (Supabase, Faro, etc.)

---

## Writing Tests

### Basic Test Structure

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import MyComponent from '@/components/MyComponent.vue';

describe('MyComponent', () => {
  it('renders correctly', () => {
    const wrapper = mount(MyComponent);
    expect(wrapper.find('h1').text()).toBe('Hello');
  });
});
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| `mount()` | Creates a real component instance |
| `wrapper.find()` | Queries DOM by CSS selector |
| `wrapper.trigger()` | Simulates user events (click, submit) |
| `wrapper.setValue()` | Types into form inputs |
| `wrapper.emitted()` | Gets events the component emitted |
| `vi.fn()` | Creates a mock function |
| `vi.mock()` | Replaces an entire module |
| `flushPromises()` | Waits for async operations |

### Testing Components with Stores

```javascript
// Create a mock store
const mockAuthStore = {
  state: { loading: false, error: null },
  login: vi.fn(() => Promise.resolve({ success: true })),
  clearError: vi.fn(),
};

// Mock the store module
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

// Mount component - it will use the mock store
const wrapper = mount(LoginForm);
```

### Testing User Interactions

```javascript
it('submits form with user input', async () => {
  const wrapper = mount(LoginForm);

  // Type in form fields
  await wrapper.find('[data-testid="username-input"]').setValue('testuser');
  await wrapper.find('[data-testid="password-input"]').setValue('password123');

  // Submit the form
  await wrapper.find('form').trigger('submit');

  // Wait for async operations
  await flushPromises();

  // Verify the result
  expect(mockAuthStore.login).toHaveBeenCalledWith('testuser', 'password123');
});
```

### Testing Emitted Events

```javascript
it('emits login-success on successful login', async () => {
  const wrapper = mount(LoginForm);

  await wrapper.find('form').trigger('submit');
  await flushPromises();

  // Check component emitted the event
  expect(wrapper.emitted('login-success')).toBeTruthy();
});
```

---

## Current Test Coverage

### Components Tested

| Component | Tests | Status |
|-----------|-------|--------|
| LoginForm.vue | 19 tests | ✅ Complete |
| AuthNav.vue | 0 tests | ⏳ Planned |
| LeagueTable.vue | 0 tests | ⏳ Planned |
| MatchesView.vue | 0 tests | ⏳ Planned |

### Running Coverage Report

```bash
npm run test:coverage
```

This generates:
- Terminal output with coverage summary
- HTML report in `coverage/` directory

---

## Best Practices

### 1. Use data-testid Attributes

Add `data-testid` attributes to elements you need to query in tests:

```html
<button data-testid="submit-button">Submit</button>
```

```javascript
wrapper.find('[data-testid="submit-button"]')
```

This is more stable than class names or text content.

### 2. Test Behavior, Not Implementation

**Good:** Test what the user sees and does
```javascript
it('shows error message when login fails', () => {
  // ...
});
```

**Avoid:** Testing internal component details
```javascript
it('sets isLoading to true', () => {
  // Too implementation-specific
});
```

### 3. Keep Tests Independent

Each test should work in isolation. Use `beforeEach` to reset state:

```javascript
beforeEach(() => {
  mockAuthStore = createMockAuthStore();
});
```

### 4. Use Descriptive Test Names

```javascript
// Good
it('disables submit button while form is loading')

// Less helpful
it('test button')
```

---

## Troubleshooting

### "Cannot find module" Errors

Ensure `vitest.config.js` has the same path aliases as `vite.config.js`:

```javascript
resolve: {
  alias: {
    '@': fileURLToPath(new URL('./src', import.meta.url)),
  },
},
```

### Tests Hang or Timeout

Usually caused by unmocked API calls. Check that `setup.js` mocks all external dependencies.

### "localStorage is not defined"

Ensure `setup.js` is listed in `vitest.config.js`:

```javascript
test: {
  setupFiles: ['./src/__tests__/setup.js'],
}
```

---

## Adding Tests for New Components

1. Create test file: `src/__tests__/components/ComponentName.spec.js`
2. Import the component and test utilities
3. Mock any stores or external dependencies
4. Write tests for:
   - Initial rendering
   - User interactions
   - Different states (loading, error, success)
   - Emitted events

### Template

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import ComponentName from '@/components/ComponentName.vue';

describe('ComponentName', () => {
  beforeEach(() => {
    // Reset mocks
  });

  describe('rendering', () => {
    it('renders correctly', () => {
      const wrapper = mount(ComponentName);
      // assertions
    });
  });

  describe('user interactions', () => {
    it('handles click events', async () => {
      const wrapper = mount(ComponentName);
      await wrapper.find('button').trigger('click');
      // assertions
    });
  });
});
```

---

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Vue Test Utils Guide](https://test-utils.vuejs.org/)
- [Testing Vue 3 Apps](https://vuejs.org/guide/scaling-up/testing.html)

---

## History

| Date | Change |
|------|--------|
| 2025-12-28 | Added Vitest infrastructure, LoginForm tests (19 tests) |
| 2025-10-07 | Initial gap analysis (0 tests existed) |
