/**
 * CSRF token management utilities
 */

import { getApiBaseUrl } from '../config/api';

let csrfToken = null;

/**
 * Fetch CSRF token from the backend
 */
export async function fetchCSRFToken() {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/csrf-token`, {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch CSRF token');
    }

    const data = await response.json();
    csrfToken = data.csrf_token;
    return csrfToken;
  } catch (error) {
    console.error('Error fetching CSRF token:', error);
    throw error;
  }
}

/**
 * Get current CSRF token, fetching if necessary
 */
export async function getCSRFToken() {
  if (!csrfToken) {
    await fetchCSRFToken();
  }
  return csrfToken;
}

/**
 * Add CSRF token to headers
 */
export async function addCSRFHeader(headers = {}) {
  const token = await getCSRFToken();
  return {
    ...headers,
    'X-CSRF-Token': token,
  };
}

/**
 * Clear stored CSRF token (call on logout)
 */
export function clearCSRFToken() {
  csrfToken = null;
}
