import { reactive, computed } from 'vue';
import { addCSRFHeader, clearCSRFToken } from '../utils/csrf';

// Remove Supabase client - using backend API instead

// API URL from environment variable
const API_URL = process.env.VUE_APP_API_URL || 'http://localhost:8000';

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
  const isTeamManager = computed(() => state.profile?.role === 'team-manager');
  const canManageTeam = computed(() => isAdmin.value || isTeamManager.value);
  const userRole = computed(() => state.profile?.role || 'team-fan');
  const userTeamId = computed(() => state.profile?.team_id);

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
  };

  const signup = async (username, password, displayName, email = null) => {
    try {
      setLoading(true);
      clearError();

      const response = await fetch(`${API_URL}/api/auth/signup`, {
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
        throw new Error(errorData.detail || 'Signup failed');
      }

      const data = await response.json();
      return { success: true, message: data.message || 'Signup successful!' };
    } catch (error) {
      setError(error.message);
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

      const response = await fetch(`${API_URL}/api/auth/signup`, {
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
        throw new Error(errorData.detail || 'Signup failed');
      }

      const data = await response.json();
      return { success: true, message: data.message || 'Signup successful!' };
    } catch (error) {
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const login = async (username, password) => {
    try {
      setLoading(true);
      clearError();

      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();

      setUser(data.user);
      setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });
      setProfile(data.user);

      // Store tokens for API calls
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      return { success: true, user: data.user };
    } catch (error) {
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      setLoading(true);

      // Call backend logout endpoint
      await apiCall(`${API_URL}/api/auth/logout`, {
        method: 'POST',
      });

      // Clear local state regardless of API response
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('sb-localhost-auth-token');
      clearCSRFToken();

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

      const response = await apiCall(`${API_URL}/api/auth/me`);
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

      const response = await apiCall(`${API_URL}/api/auth/profile`, {
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

      // Get current user info from backend
      const response = await apiCall(`${API_URL}/api/auth/me`);

      if (response && response.success) {
        setUser(response.user);
        setProfile(response.user.profile);
        setSession({ access_token: token }); // Minimal session object
      } else {
        // Invalid token, clear storage
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
    const token = localStorage.getItem('auth_token');
    const defaultHeaders = {
      'Content-Type': 'application/json',
    };

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
          if (retryResponse.ok) {
            return retryResponse.json();
          }
        }
      }
      // Refresh failed or retry failed, force logout
      await logout();
      throw new Error('Session expired. Please log in again.');
    }

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
        throw new Error('No refresh token');
      }

      const response = await fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      setSession(data.session);

      return { success: true };
    } catch (error) {
      // Refresh failed, force logout
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.clear();
      return { success: false, error: error.message };
    }
  };

  const apiRequest = async (url, options = {}) => {
    // Add CSRF headers for state-changing methods
    let headers = {
      ...getAuthHeaders(),
      ...options.headers,
    };

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
        `${API_URL}/api/auth/username-available/${username}`,
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
    isTeamManager,
    canManageTeam,
    userRole,
    userTeamId,

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
