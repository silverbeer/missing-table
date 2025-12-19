import { reactive, computed } from 'vue';
import { addCSRFHeader, clearCSRFToken } from '../utils/csrf';
import { getTraceHeaders } from '../utils/traceContext';
import { getApiBaseUrl } from '../config/api';
import { supabase, getOAuthRedirectUrl } from '../config/supabase';
import {
  recordLogin,
  recordLoginDuration,
  recordSignup,
  recordLogout,
  recordSessionRefresh,
  recordHttpRequest,
  setFaroUser,
  clearFaroUser,
} from '../faro';

// Supabase client imported for OAuth only - regular API calls go through backend

// Auth store
const state = reactive({
  user: null,
  session: null,
  profile: null,
  loading: false,
  error: null,
});

export const useAuthStore = () => {
  // Computed properties
  const isAuthenticated = computed(() => !!state.session);
  const isAdmin = computed(() => state.profile?.role === 'admin');
  const isClubManager = computed(() => state.profile?.role === 'club_manager');
  const isTeamManager = computed(
    () =>
      state.profile?.role === 'team-manager' ||
      state.profile?.role === 'team_manager'
  );
  const isPlayer = computed(() => state.profile?.role === 'team-player');
  // Players can browse all leagues/divisions but not edit
  const canBrowseAll = computed(() => isAdmin.value || isPlayer.value);
  const canManageTeam = computed(
    () => isAdmin.value || isClubManager.value || isTeamManager.value
  );
  const canManageClub = computed(() => isAdmin.value || isClubManager.value);
  const userRole = computed(() => state.profile?.role || 'team-fan');
  const userTeamId = computed(() => state.profile?.team_id);
  const userClubId = computed(() => state.profile?.club_id);

  // Actions
  const setLoading = loading => {
    state.loading = loading;
  };

  const setError = error => {
    state.error = error;
  };

  const clearError = () => {
    state.error = null;
  };

  const setUser = user => {
    state.user = user;
  };

  const setSession = session => {
    state.session = session;
    if (session?.access_token) {
      localStorage.setItem('auth_token', session.access_token);
      if (session.refresh_token) {
        localStorage.setItem('refresh_token', session.refresh_token);
      }
    } else {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
    }
  };

  const setProfile = profile => {
    state.profile = profile;
    if (profile) {
      localStorage.setItem('auth_profile', JSON.stringify(profile));
    } else {
      localStorage.removeItem('auth_profile');
    }
  };

  const signup = async (username, password, displayName, email = null) => {
    try {
      setLoading(true);
      clearError();

      const response = await fetch(`${getApiBaseUrl()}/api/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getTraceHeaders(),
        },
        body: JSON.stringify({
          username,
          password,
          display_name: displayName || username,
          email, // Optional email for notifications
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        recordSignup(false, 'signup', { error_type: 'signup_failed' });
        throw new Error(errorData.detail || 'Signup failed');
      }

      const data = await response.json();
      recordSignup(true, 'signup');
      return { success: true, message: data.message || 'Signup successful!' };
    } catch (error) {
      setError(error.message);
      recordSignup(false, 'signup', { error_type: 'exception' });
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const signupWithInvite = async (
    username,
    password,
    displayName,
    inviteCode,
    email = null
  ) => {
    try {
      setLoading(true);
      clearError();

      const response = await fetch(`${getApiBaseUrl()}/api/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getTraceHeaders(),
        },
        body: JSON.stringify({
          username,
          password,
          display_name: displayName || username,
          invite_code: inviteCode,
          email, // Optional email for notifications
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        recordSignup(false, 'signup_with_invite', {
          error_type: 'signup_failed',
        });
        throw new Error(errorData.detail || 'Signup failed');
      }

      const data = await response.json();
      recordSignup(true, 'signup_with_invite');
      return { success: true, message: data.message || 'Signup successful!' };
    } catch (error) {
      setError(error.message);
      recordSignup(false, 'signup_with_invite', { error_type: 'exception' });
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const login = async (username, password) => {
    const startTime = performance.now();
    try {
      setLoading(true);
      clearError();

      const response = await fetch(`${getApiBaseUrl()}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getTraceHeaders(),
        },
        body: JSON.stringify({ username, password }),
      });

      const duration = performance.now() - startTime;

      if (!response.ok) {
        const errorData = await response.json();
        recordLogin(false, { error_type: 'invalid_credentials' });
        recordLoginDuration(duration, false);
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();

      setUser(data.user);
      setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });
      // Login endpoint returns basic user info
      setProfile(data.user);

      // Store tokens for API calls
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      console.log('Login successful - Basic profile set:', data.user);

      // Fetch complete profile (includes photos, personal info, etc.)
      await fetchProfile();
      console.log('Complete profile fetched:', state.profile);

      // Record successful login metrics and set user context for observability
      recordLogin(true, { user_role: data.user.role || 'team-fan' });
      recordLoginDuration(duration, true);
      setFaroUser(data.user.id, { role: data.user.role || 'team-fan' });

      return { success: true, user: data.user };
    } catch (error) {
      const duration = performance.now() - startTime;
      setError(error.message);
      recordLogin(false, { error_type: 'exception' });
      recordLoginDuration(duration, false);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  // OAuth Social Login with Google (requires invite code for signup)
  const signInWithGoogle = async (inviteCode = null) => {
    try {
      setLoading(true);
      clearError();

      if (!inviteCode) {
        throw new Error('Invite code is required for Google sign-up');
      }

      const redirectTo = getOAuthRedirectUrl();
      console.log('Starting Google OAuth, redirect URL:', redirectTo);

      // Store invite code in localStorage to retrieve after OAuth callback
      // (OAuth state parameter is limited and can be unreliable across redirects)
      localStorage.setItem('oauth_invite_code', inviteCode);

      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });

      if (error) {
        localStorage.removeItem('oauth_invite_code');
        recordLogin(false, { error_type: 'oauth_initiation_failed' });
        throw new Error(error.message);
      }

      // User will be redirected to Google, then back to our callback URL
      // The callback handler will complete the authentication
      return { success: true, url: data.url };
    } catch (error) {
      setError(error.message);
      recordLogin(false, { error_type: 'oauth_exception' });
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  // Handle OAuth callback - called after redirect back from Google
  const handleOAuthCallback = async () => {
    try {
      setLoading(true);
      clearError();

      // Retrieve invite code stored before OAuth redirect
      const inviteCode = localStorage.getItem('oauth_invite_code');
      localStorage.removeItem('oauth_invite_code'); // Clean up immediately

      if (!inviteCode) {
        throw new Error(
          'No invite code found. Please start the signup process again with your invite code.'
        );
      }

      // Get the session from the URL hash (Supabase puts tokens there)
      const { data, error } = await supabase.auth.getSession();

      if (error) {
        throw new Error(error.message);
      }

      if (!data.session) {
        throw new Error('No session found after OAuth callback');
      }

      // Store the tokens
      setSession({
        access_token: data.session.access_token,
        refresh_token: data.session.refresh_token,
      });

      // Now verify with our backend and get/create user profile
      // Pass the invite code for validation
      const response = await fetch(
        `${getApiBaseUrl()}/api/auth/oauth/callback`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${data.session.access_token}`,
            ...getTraceHeaders(),
          },
          body: JSON.stringify({
            access_token: data.session.access_token,
            refresh_token: data.session.refresh_token,
            provider: 'google',
            invite_code: inviteCode,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'OAuth callback failed');
      }

      const userData = await response.json();

      setUser(userData.user);
      setProfile(userData.user);

      // Record successful OAuth login
      recordLogin(true, {
        user_role: userData.user.role || 'team-fan',
        provider: 'google',
      });
      setFaroUser(userData.user.id, { role: userData.user.role || 'team-fan' });

      return { success: true, user: userData.user };
    } catch (error) {
      setError(error.message);
      recordLogin(false, { error_type: 'oauth_callback_failed' });
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      setLoading(true);

      // Call backend logout endpoint using plain fetch (not apiCall to avoid infinite loop)
      const token = localStorage.getItem('auth_token');
      if (token) {
        try {
          await fetch(`${getApiBaseUrl()}/api/auth/logout`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
        } catch (e) {
          // Ignore logout endpoint errors - we'll clear local state anyway
          console.warn('Logout endpoint error (ignored):', e);
        }
      }

      // Clear local state regardless of API response
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('sb-localhost-auth-token');
      clearCSRFToken();

      // Record logout metric and clear user context
      recordLogout();
      clearFaroUser();

      return { success: true };
    } catch (error) {
      // Still clear local state on error
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.clear();
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const forceLogout = () => {
    // Force clear all auth state without async calls
    state.user = null;
    state.session = null;
    state.profile = null;
    state.loading = false;
    state.error = null;
    localStorage.clear();
    sessionStorage.clear();
  };

  const fetchProfile = async () => {
    try {
      if (!state.session) return;

      const response = await apiCall(`${getApiBaseUrl()}/api/auth/me`);
      if (response && response.success) {
        setProfile(response.user.profile);
        return response.user.profile;
      } else {
        console.warn('No profile found for user');
        return null;
      }
    } catch (error) {
      console.error('Error fetching profile:', error);
      setError(error.message);
    }
  };

  const updateProfile = async updates => {
    try {
      setLoading(true);
      clearError();

      const response = await apiCall(`${getApiBaseUrl()}/api/auth/profile`, {
        method: 'PUT',
        body: JSON.stringify({
          ...updates,
          updated_at: new Date().toISOString(),
        }),
      });

      if (response && response.success) {
        // Refresh profile
        await fetchProfile();
        return { success: true, data: response.data };
      } else {
        throw new Error(response?.detail || 'Profile update failed');
      }
    } catch (error) {
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const initialize = async () => {
    try {
      setLoading(true);

      // Check for existing token
      const token = localStorage.getItem('auth_token');
      if (!token) {
        return;
      }

      // Don't set session until verification succeeds
      // This prevents showing authenticated content while verifying

      // Get current user info from backend (verify token)
      const response = await fetch(`${getApiBaseUrl()}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          ...getTraceHeaders(),
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data && data.success) {
          setUser(data.user);
          // /api/auth/me returns role/team_id nested in user.profile
          const profileData = data.user.profile || data.user;
          setProfile(profileData);
          setSession({ access_token: token }); // Only set session after verification
          console.log('Initialize - Profile loaded:', profileData);
        } else {
          // Invalid response, clear storage
          localStorage.clear();
        }
      } else if (response.status === 401) {
        // Token expired, try to refresh
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const refreshResult = await refreshSession();
          if (refreshResult.success) {
            // Retry initialization with new token
            const newToken = localStorage.getItem('auth_token');
            const retryResponse = await fetch(
              `${getApiBaseUrl()}/api/auth/me`,
              {
                headers: {
                  Authorization: `Bearer ${newToken}`,
                  'Content-Type': 'application/json',
                  ...getTraceHeaders(),
                },
              }
            );
            if (retryResponse.ok) {
              const retryData = await retryResponse.json();
              if (retryData && retryData.success) {
                setUser(retryData.user);
                const profileData = retryData.user.profile || retryData.user;
                setProfile(profileData);
                setSession({ access_token: newToken });
                console.log(
                  'Initialize - Profile loaded after refresh:',
                  profileData
                );
                return;
              }
            }
          }
        }
        // Refresh failed or no refresh token, clear storage
        localStorage.clear();
      } else {
        // Other error, clear storage
        localStorage.clear();
      }
    } catch (error) {
      console.error('Auth initialization error:', error);
      localStorage.clear();
    } finally {
      setLoading(false);
    }
  };

  // API helpers with auth headers
  const getAuthHeaders = () => {
    const token = localStorage.getItem('auth_token');
    return {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...getTraceHeaders(), // Include session_id and request_id for distributed tracing
    };
  };

  // NEW: Simple API call helper with auth headers
  const apiCall = async (endpoint, options = {}) => {
    const startTime = performance.now();
    const method = options.method || 'GET';
    const token = localStorage.getItem('auth_token');
    const traceHeaders = getTraceHeaders(); // Generate trace IDs for this request
    const defaultHeaders = { ...traceHeaders };

    // Only set Content-Type for non-FormData requests
    // FormData needs the browser to set Content-Type with boundary automatically
    if (!(options.body instanceof FormData)) {
      defaultHeaders['Content-Type'] = 'application/json';
    }

    if (token) {
      defaultHeaders.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(endpoint, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });

    const duration = performance.now() - startTime;

    if (response.status === 401) {
      // Token expired, try refresh
      const refreshResult = await refreshSession();
      if (refreshResult.success) {
        // Retry original request
        const retryToken = localStorage.getItem('auth_token');
        if (retryToken) {
          defaultHeaders.Authorization = `Bearer ${retryToken}`;
          const retryResponse = await fetch(endpoint, {
            ...options,
            headers: {
              ...defaultHeaders,
              ...options.headers,
            },
          });
          const retryDuration = performance.now() - startTime;
          if (retryResponse.ok) {
            recordHttpRequest(
              endpoint,
              method,
              retryResponse.status,
              retryDuration
            );
            return retryResponse.json();
          }
          recordHttpRequest(
            endpoint,
            method,
            retryResponse.status,
            retryDuration
          );
        }
      }
      // Refresh failed or retry failed, force logout
      recordHttpRequest(endpoint, method, 401, duration);
      await logout();
      throw new Error('Session expired. Please log in again.');
    }

    // Record HTTP request metrics
    recordHttpRequest(endpoint, method, response.status, duration);

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: 'Network error' }));
      throw new Error(error.detail || error.message || 'Request failed');
    }

    return response.json();
  };

  const isTokenExpiringSoon = () => {
    if (!state.session?.expires_at) return false;
    const expiresAt = new Date(state.session.expires_at * 1000);
    const now = new Date();
    const timeUntilExpiry = expiresAt.getTime() - now.getTime();
    // Return true if token expires in less than 5 minutes
    return timeUntilExpiry < 5 * 60 * 1000;
  };

  const refreshSession = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        recordSessionRefresh(false);
        throw new Error('No refresh token');
      }

      const response = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getTraceHeaders(),
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        recordSessionRefresh(false);
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      setSession(data.session);

      recordSessionRefresh(true);
      return { success: true };
    } catch (error) {
      // Refresh failed, force logout
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.clear();
      recordSessionRefresh(false);
      return { success: false, error: error.message };
    }
  };

  const apiRequest = async (url, options = {}) => {
    // For FormData, don't set Content-Type - browser sets it with boundary
    const isFormData = options.body instanceof FormData;
    const token = localStorage.getItem('auth_token');

    let headers = {
      Authorization: `Bearer ${token}`,
      ...getTraceHeaders(), // Include trace IDs for distributed tracing
      ...options.headers,
    };

    // Only add Content-Type for non-FormData requests
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }

    if (
      ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method?.toUpperCase())
    ) {
      headers = await addCSRFHeader(headers);
    }

    // Use the simpler apiCall helper
    return apiCall(url, { ...options, headers });
  };

  const checkUsernameAvailability = async username => {
    try {
      const response = await fetch(
        `${getApiBaseUrl()}/api/auth/username-available/${username}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...getTraceHeaders(),
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to check username availability');
      }

      const data = await response.json();
      return data; // Returns { available, message, suggestions? }
    } catch (error) {
      console.error('Username availability check error:', error);
      return { available: false, message: 'Error checking username' };
    }
  };

  return {
    // State
    state,

    // Computed
    isAuthenticated,
    isAdmin,
    isClubManager,
    isTeamManager,
    isPlayer,
    canBrowseAll,
    canManageTeam,
    canManageClub,
    userRole,
    userTeamId,
    userClubId,

    // Actions
    signup,
    signupWithInvite,
    login,
    signInWithGoogle,
    handleOAuthCallback,
    logout,
    forceLogout,
    fetchProfile,
    updateProfile,
    initialize,
    setError,
    clearError,

    // Helpers
    getAuthHeaders,
    apiRequest,
    apiCall,
    refreshSession,
    isTokenExpiringSoon,
    checkUsernameAvailability,
  };
};
