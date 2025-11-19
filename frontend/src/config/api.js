// API Configuration
// Centralized configuration for API endpoints

const getApiUrl = () => {
  // ALWAYS use runtime detection in browser (ignore build-time env vars)
  // This ensures browser uses the correct URL regardless of how it was built
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;

    // If running on localhost, use local backend
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8000';
    }

    // For cloud deployment, use same domain (ingress routes /api to backend)
    // Works for: dev.missingtable.com, missingtable.com, www.missingtable.com
    return `${protocol}//${hostname}`;
  }

  // SSR/build-time fallback only (never executed in browser)
  return 'http://localhost:8000';
};

// CRITICAL: Must be a getter function, NOT a constant!
// Constants are evaluated at BUILD time (Node.js, no window), getters at RUNTIME (browser)
export const getApiBaseUrl = () => getApiUrl();

// For backwards compatibility, export as property that calls getter
export const API_BASE_URL = getApiUrl();

// Helper to build API URL at runtime
const buildUrl = (path) => `${getApiUrl()}${path}`;

export const API_ENDPOINTS = {
  get AUTH() {
    const base = getApiUrl();
    return {
      SIGNUP: `${base}/api/auth/signup`,
      LOGIN: `${base}/api/auth/login`,
      LOGOUT: `${base}/api/auth/logout`,
      PROFILE: `${base}/api/profile`,
    };
  },
  get INVITES() {
    const base = getApiUrl();
    return {
      VALIDATE: code => `${base}/api/invites/validate/${code}`,
      MY_INVITES: `${base}/api/invites/my-invites`,
      ADMIN_TEAM_MANAGER: `${base}/api/invites/admin/team-manager`,
      ADMIN_TEAM_PLAYER: `${base}/api/invites/admin/team-player`,
      ADMIN_TEAM_FAN: `${base}/api/invites/admin/team-fan`,
      TEAM_MANAGER_PLAYER: `${base}/api/invites/team-manager/team-player`,
      TEAM_MANAGER_FAN: `${base}/api/invites/team-manager/team-fan`,
      CANCEL: id => `${base}/api/invites/${id}`,
    };
  },
  get TEAMS() { return buildUrl('/api/teams'); },
  get AGE_GROUPS() { return buildUrl('/api/age-groups'); },
  get SEASONS() { return buildUrl('/api/seasons'); },
  get MATCHES() { return buildUrl('/api/matches'); },
};

console.log('API Configuration:', {
  API_BASE_URL,
  env: process.env.VUE_APP_API_URL,
});
