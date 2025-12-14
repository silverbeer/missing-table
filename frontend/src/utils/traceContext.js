/**
 * Trace Context - Session and Request ID Management
 *
 * Provides distributed tracing support for correlating frontend actions
 * with backend processing in Grafana Loki.
 *
 * Session ID: Persists for browser session, correlates all user actions
 * Request ID: Unique per API call, correlates single request through backend
 */

const SESSION_ID_KEY = 'mt_session_id';

/**
 * Generate a short unique ID (8 hex characters)
 * 8 chars = 4.3 billion combinations, plenty for session/request scope
 * @returns {string} Short hex ID
 */
function generateShortId() {
  // Use crypto.randomUUID if available, take first 8 chars
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, '').substring(0, 8);
  }

  // Fallback for older browsers
  return 'xxxxxxxx'.replace(/x/g, () => {
    return ((Math.random() * 16) | 0).toString(16);
  });
}

/**
 * Get or create the session ID
 * Session ID persists across page loads but not browser sessions
 *
 * @returns {string} Session ID in format "mt-sess-{8 hex chars}"
 */
export function getSessionId() {
  // Check sessionStorage first
  let sessionId = sessionStorage.getItem(SESSION_ID_KEY);

  if (!sessionId) {
    sessionId = `mt-sess-${generateShortId()}`;
    sessionStorage.setItem(SESSION_ID_KEY, sessionId);

    // Log session start for debugging
    console.log('[TraceContext] New session started:', sessionId);
  }

  return sessionId;
}

/**
 * Generate a unique request ID for an API call
 *
 * @returns {string} Request ID in format "mt-req-{8 hex chars}"
 */
export function generateRequestId() {
  return `mt-req-${generateShortId()}`;
}

/**
 * Get trace headers to include in API requests
 *
 * @returns {Object} Headers object with X-Session-ID and X-Request-ID
 */
export function getTraceHeaders() {
  return {
    'X-Session-ID': getSessionId(),
    'X-Request-ID': generateRequestId(),
  };
}

/**
 * Create a fetch wrapper that automatically includes trace headers
 *
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} Fetch response
 */
export async function tracedFetch(url, options = {}) {
  const traceHeaders = getTraceHeaders();

  const mergedOptions = {
    ...options,
    headers: {
      ...traceHeaders,
      ...options.headers,
    },
  };

  return fetch(url, mergedOptions);
}

/**
 * Get current trace context for logging
 * Use this when manually logging events via Faro
 *
 * @param {string} [requestId] - Optional specific request ID
 * @returns {Object} Trace context for logging
 */
export function getTraceContext(requestId = null) {
  return {
    session_id: getSessionId(),
    request_id: requestId || generateRequestId(),
  };
}

// Initialize session ID on module load
// This ensures consistent session tracking from first API call
if (typeof window !== 'undefined') {
  getSessionId();
}
