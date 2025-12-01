import { reactive, computed } from 'vue';
import { addCSRFHeader, clearCSRFToken } from '../utils/csrf';
import { getApiBaseUrl } from '../config/api';
import {
  recordLogin,
  recordLoginDuration,
  recordSignup,
  recordLogout,
  recordSessionRefresh,
  recordHttpRequest,
} from '../telemetry';

// Remove Supabase client - using backend API instead

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

      // Record successful login metrics
      recordLogin(true, { user_role: data.user.role || 'team-fan' });
      recordLoginDuration(duration, true);

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

      // Record logout metric
      recordLogout();

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
    };
  };

  // NEW: Simple API call helper with auth headers
  const apiCall = async (endpoint, options = {}) => {
    const startTime = performance.now();
    const method = options.method || 'GET';
    const token = localStorage.getItem('auth_token');
    const defaultHeaders = {};

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
    canManageTeam,
    canManageClub,
    userRole,
    userTeamId,
    userClubId,

    // Actions
    signup,
    signupWithInvite,
    login,
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
