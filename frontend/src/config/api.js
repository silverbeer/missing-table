// API Configuration
// Centralized configuration for API endpoints

const getApiUrl = () => {
  // Try to get from environment variable first
  const envApiUrl = process.env.VUE_APP_API_URL;

  if (envApiUrl) {
    return envApiUrl;
  }

  // Fallback based on current location
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;

    // If running on localhost, use local backend
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8000';
    }

    // For production, construct API URL based on current domain
    return `${protocol}//${hostname.replace('frontend', 'backend')}`;
  }

  // Ultimate fallback
  return 'http://localhost:8000';
};

export const API_BASE_URL = getApiUrl();
export const API_ENDPOINTS = {
  AUTH: {
    SIGNUP: `${API_BASE_URL}/api/auth/signup`,
    LOGIN: `${API_BASE_URL}/api/auth/login`,
    LOGOUT: `${API_BASE_URL}/api/auth/logout`,
    PROFILE: `${API_BASE_URL}/api/profile`,
  },
  INVITES: {
    VALIDATE: code => `${API_BASE_URL}/api/invites/validate/${code}`,
    MY_INVITES: `${API_BASE_URL}/api/invites/my-invites`,
    ADMIN_TEAM_MANAGER: `${API_BASE_URL}/api/invites/admin/team-manager`,
    ADMIN_TEAM_PLAYER: `${API_BASE_URL}/api/invites/admin/team-player`,
    ADMIN_TEAM_FAN: `${API_BASE_URL}/api/invites/admin/team-fan`,
    TEAM_MANAGER_PLAYER: `${API_BASE_URL}/api/invites/team-manager/team-player`,
    TEAM_MANAGER_FAN: `${API_BASE_URL}/api/invites/team-manager/team-fan`,
    CANCEL: id => `${API_BASE_URL}/api/invites/${id}`,
  },
  TEAMS: `${API_BASE_URL}/api/teams`,
  AGE_GROUPS: `${API_BASE_URL}/api/age-groups`,
  SEASONS: `${API_BASE_URL}/api/seasons`,
  MATCHES: `${API_BASE_URL}/api/matches`,
};

console.log('API Configuration:', {
  API_BASE_URL,
  env: process.env.VUE_APP_API_URL,
});
