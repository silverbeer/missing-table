/**
 * LoginForm.vue Tests
 *
 * This file tests the LoginForm component.
 *
 * TESTING PHILOSOPHY:
 * - Test behavior, not implementation details
 * - Test what the user sees and does
 * - Mock external dependencies (API, stores)
 *
 * STRUCTURE:
 * - describe() groups related tests
 * - it() (or test()) defines a single test case
 * - expect() makes assertions about what should happen
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import LoginForm from '@/components/LoginForm.vue';

// =============================================================================
// TEST SETUP
// =============================================================================

/**
 * Create a mock auth store
 *
 * The LoginForm component calls useAuthStore() to get the auth store.
 * In tests, we provide a fake store so we can:
 * 1. Control what the store returns
 * 2. Verify the component calls store methods correctly
 * 3. Avoid making real API calls
 */
const createMockAuthStore = (overrides = {}) => ({
  // Reactive state the component reads
  state: {
    loading: false,
    error: null,
    user: null,
    session: null,
    ...overrides.state,
  },

  // Methods the component calls
  login: vi.fn(() => Promise.resolve({ success: true })),
  signupWithInvite: vi.fn(() => Promise.resolve({ success: true })),
  signInWithGoogle: vi.fn(() => Promise.resolve({ success: true })),
  clearError: vi.fn(),
  setError: vi.fn(),
  updateProfile: vi.fn(() => Promise.resolve({ success: true })),

  // Allow overriding any of the above
  ...overrides,
});

// Variable to hold our mock store for each test
let mockAuthStore;

/**
 * Mock the auth store module
 *
 * When LoginForm imports useAuthStore, it gets our mock instead.
 * This is "module mocking" - we replace the entire module.
 */
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

/**
 * Helper function to mount the component
 *
 * mount() creates a real instance of the component that we can interact with.
 * We wrap it in a helper so each test can easily customize the setup.
 *
 * @param {Object} options - Vue Test Utils mount options
 * @returns {Wrapper} - The mounted component wrapper
 */
const mountLoginForm = (options = {}) => {
  return mount(LoginForm, {
    global: {
      // Stub child components we don't want to render
      stubs: {
        // If LoginForm used other components, we'd stub them here
      },
    },
    ...options,
  });
};

// =============================================================================
// TESTS: RENDERING
// =============================================================================

describe('LoginForm', () => {
  // Reset the mock store before each test
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
  });

  describe('initial rendering', () => {
    /**
     * Test: Component renders login form by default
     *
     * What we're testing:
     * - The component mounts without errors
     * - Default state shows "Login" (not signup)
     * - Required form elements are present
     */
    it('renders login form by default', () => {
      // Arrange & Act: Mount the component
      const wrapper = mountLoginForm();

      // Assert: Check the heading says "Login"
      expect(wrapper.find('h2').text()).toBe('Login');

      // Assert: Check form inputs exist using data-testid attributes
      // (data-testid is a convention for targeting elements in tests)
      expect(wrapper.find('[data-testid="username-input"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="password-input"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="login-button"]').exists()).toBe(true);
    });

    /**
     * Test: Shows signup link for users with invite codes
     */
    it('shows signup link in footer', () => {
      const wrapper = mountLoginForm();

      // Find the signup link
      const signupLink = wrapper.find('[data-testid="signup-link"]');
      expect(signupLink.exists()).toBe(true);
      expect(signupLink.text()).toContain('Sign Up');
    });

    /**
     * Test: Shows Google login button on login form
     */
    it('shows Google login button', () => {
      const wrapper = mountLoginForm();

      const googleButton = wrapper.find('[data-testid="google-login-button"]');
      expect(googleButton.exists()).toBe(true);
      expect(googleButton.text()).toContain('Continue with Google');
    });
  });

  // ===========================================================================
  // TESTS: FORM SWITCHING
  // ===========================================================================

  describe('form switching', () => {
    /**
     * Test: Clicking signup link switches to signup form
     *
     * This tests user interaction:
     * 1. User sees login form
     * 2. User clicks "Sign Up" link
     * 3. Form changes to show signup fields
     */
    it('switches to signup form when clicking signup link', async () => {
      const wrapper = mountLoginForm();

      // Initially shows "Login"
      expect(wrapper.find('h2').text()).toBe('Login');

      // Click the signup link
      await wrapper.find('[data-testid="signup-link"]').trigger('click');

      // Now shows "Sign Up with Invite"
      expect(wrapper.find('h2').text()).toBe('Sign Up with Invite');

      // Invite code field should now be visible
      expect(wrapper.find('#inviteCode').exists()).toBe(true);
    });

    /**
     * Test: Can switch back to login form
     */
    it('switches back to login form when clicking login link', async () => {
      const wrapper = mountLoginForm();

      // Switch to signup
      await wrapper.find('[data-testid="signup-link"]').trigger('click');
      expect(wrapper.find('h2').text()).toBe('Sign Up with Invite');

      // Switch back to login
      await wrapper.find('[data-testid="login-link"]').trigger('click');
      expect(wrapper.find('h2').text()).toBe('Login');
    });

    /**
     * Test: Clears errors when switching forms
     */
    it('clears error when switching forms', async () => {
      const wrapper = mountLoginForm();

      // Switch to signup
      await wrapper.find('[data-testid="signup-link"]').trigger('click');

      // Verify clearError was called
      expect(mockAuthStore.clearError).toHaveBeenCalled();
    });
  });

  // ===========================================================================
  // TESTS: LOGIN FLOW
  // ===========================================================================

  describe('login flow', () => {
    /**
     * Test: Submitting login form calls authStore.login
     *
     * What we verify:
     * 1. User can type username and password
     * 2. Submitting form calls login() with correct values
     * 3. Success emits 'login-success' event
     */
    it('calls login with username and password', async () => {
      const wrapper = mountLoginForm();

      // Type in the form fields
      // setValue() simulates user typing
      await wrapper.find('[data-testid="username-input"]').setValue('testuser');
      await wrapper
        .find('[data-testid="password-input"]')
        .setValue('password123');

      // Submit the form
      await wrapper.find('form').trigger('submit');

      // Wait for any promises to resolve (login is async)
      await flushPromises();

      // Verify login was called with correct arguments
      expect(mockAuthStore.login).toHaveBeenCalledWith(
        'testuser',
        'password123'
      );
    });

    /**
     * Test: Emits login-success event on successful login
     */
    it('emits login-success on successful login', async () => {
      const wrapper = mountLoginForm();

      await wrapper.find('[data-testid="username-input"]').setValue('testuser');
      await wrapper
        .find('[data-testid="password-input"]')
        .setValue('password123');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      // Check that the component emitted the event
      expect(wrapper.emitted('login-success')).toBeTruthy();
    });

    /**
     * Test: Does not emit login-success when login fails
     */
    it('does not emit login-success on failed login', async () => {
      // Override login to return failure
      mockAuthStore.login = vi.fn(() =>
        Promise.resolve({ success: false, error: 'Invalid credentials' })
      );

      const wrapper = mountLoginForm();

      await wrapper.find('[data-testid="username-input"]').setValue('testuser');
      await wrapper.find('[data-testid="password-input"]').setValue('wrong');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      // No login-success event should be emitted
      expect(wrapper.emitted('login-success')).toBeFalsy();
    });
  });

  // ===========================================================================
  // TESTS: SIGNUP FLOW
  // ===========================================================================

  describe('signup flow', () => {
    /**
     * Test: Signup form shows additional fields
     */
    it('shows invite code and optional fields in signup mode', async () => {
      const wrapper = mountLoginForm();

      // Switch to signup
      await wrapper.find('[data-testid="signup-link"]').trigger('click');

      // Check for signup-specific fields
      expect(wrapper.find('#inviteCode').exists()).toBe(true);
      expect(wrapper.find('#displayName').exists()).toBe(true);
      expect(wrapper.find('#email').exists()).toBe(true);
    });

    /**
     * Test: Submitting signup form calls signupWithInvite
     */
    it('calls signupWithInvite with form data', async () => {
      const wrapper = mountLoginForm();

      // Switch to signup mode
      await wrapper.find('[data-testid="signup-link"]').trigger('click');

      // Fill out the signup form
      await wrapper.find('[data-testid="username-input"]').setValue('newuser');
      await wrapper
        .find('[data-testid="password-input"]')
        .setValue('password123');
      await wrapper.find('#inviteCode').setValue('INVITE123');
      await wrapper.find('#displayName').setValue('New User');
      await wrapper.find('#email').setValue('new@example.com');

      // Submit
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      // Verify signupWithInvite was called with all the data
      expect(mockAuthStore.signupWithInvite).toHaveBeenCalledWith(
        'newuser', // username
        'password123', // password
        'New User', // displayName
        'INVITE123', // inviteCode
        'new@example.com' // email
      );
    });

    /**
     * Test: After successful signup, auto-login is attempted
     */
    it('auto-logs in after successful signup', async () => {
      const wrapper = mountLoginForm();

      // Switch to signup
      await wrapper.find('[data-testid="signup-link"]').trigger('click');

      // Fill minimal required fields
      await wrapper.find('[data-testid="username-input"]').setValue('newuser');
      await wrapper
        .find('[data-testid="password-input"]')
        .setValue('password123');
      await wrapper.find('#inviteCode').setValue('INVITE123');

      // Submit
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      // After signup succeeds, login should be called
      expect(mockAuthStore.login).toHaveBeenCalledWith(
        'newuser',
        'password123'
      );
    });
  });

  // ===========================================================================
  // TESTS: LOADING STATE
  // ===========================================================================

  describe('loading state', () => {
    /**
     * Test: Button shows "Processing..." when loading
     */
    it('shows processing text when loading', () => {
      // Create store with loading: true
      mockAuthStore = createMockAuthStore({
        state: { loading: true, error: null },
      });

      const wrapper = mountLoginForm();

      const button = wrapper.find('[data-testid="login-button"]');
      expect(button.text()).toBe('Processing...');
    });

    /**
     * Test: Form inputs are disabled during loading
     */
    it('disables inputs when loading', () => {
      mockAuthStore = createMockAuthStore({
        state: { loading: true, error: null },
      });

      const wrapper = mountLoginForm();

      expect(
        wrapper.find('[data-testid="username-input"]').attributes('disabled')
      ).toBeDefined();
      expect(
        wrapper.find('[data-testid="password-input"]').attributes('disabled')
      ).toBeDefined();
      expect(
        wrapper.find('[data-testid="login-button"]').attributes('disabled')
      ).toBeDefined();
    });
  });

  // ===========================================================================
  // TESTS: ERROR DISPLAY
  // ===========================================================================

  describe('error display', () => {
    /**
     * Test: Displays error message from store
     */
    it('shows error message when store has error', () => {
      mockAuthStore = createMockAuthStore({
        state: { loading: false, error: 'Invalid username or password' },
      });

      const wrapper = mountLoginForm();

      const errorMessage = wrapper.find('[data-testid="error-message"]');
      expect(errorMessage.exists()).toBe(true);
      expect(errorMessage.text()).toBe('Invalid username or password');
    });

    /**
     * Test: No error message when store has no error
     */
    it('does not show error message when no error', () => {
      const wrapper = mountLoginForm();

      const errorMessage = wrapper.find('[data-testid="error-message"]');
      expect(errorMessage.exists()).toBe(false);
    });
  });

  // ===========================================================================
  // TESTS: GOOGLE LOGIN
  // ===========================================================================

  describe('Google OAuth', () => {
    /**
     * Test: Google login button calls signInWithGoogle
     */
    it('calls signInWithGoogle when clicking Google button', async () => {
      const wrapper = mountLoginForm();

      await wrapper
        .find('[data-testid="google-login-button"]')
        .trigger('click');
      await flushPromises();

      // For login flow, signInWithGoogle is called with null (no invite code)
      expect(mockAuthStore.signInWithGoogle).toHaveBeenCalledWith(null, null);
    });

    /**
     * Test: Google signup button shown after valid invite code
     *
     * Note: This test is limited because validateInviteCode makes a real fetch call.
     * In a full test, we'd mock the fetch to return invite info.
     */
    it('does not show Google signup button without valid invite', async () => {
      const wrapper = mountLoginForm();

      // Switch to signup mode
      await wrapper.find('[data-testid="signup-link"]').trigger('click');

      // Google signup button should NOT exist (no valid invite)
      const googleSignupButton = wrapper.find(
        '[data-testid="google-signup-button"]'
      );
      expect(googleSignupButton.exists()).toBe(false);
    });
  });

  // ===========================================================================
  // TESTS: URL INVITE CODE
  // ===========================================================================

  describe('URL invite code', () => {
    /**
     * Test: Pre-fills invite code from URL parameter
     *
     * When user visits: /login?code=INVITE123
     * The form should switch to signup mode and pre-fill the code
     */
    it('pre-fills invite code from URL query parameter', async () => {
      // Set the URL query string before mounting
      window.location.search = '?code=TESTCODE123';

      // Mock fetch for validateInviteCode
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            invite_type: 'team_player',
            team_name: 'Test Team',
          }),
      });

      const wrapper = mountLoginForm();

      // Wait for onMounted to complete
      await flushPromises();

      // Should be in signup mode
      expect(wrapper.find('h2').text()).toBe('Sign Up with Invite');

      // Invite code should be pre-filled
      const inviteInput = wrapper.find('#inviteCode');
      expect(inviteInput.element.value).toBe('TESTCODE123');
    });
  });
});
