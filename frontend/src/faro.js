/**
 * Grafana Faro - Frontend Observability
 *
 * Provides automatic instrumentation for:
 * - Web Vitals (LCP, INP, CLS, FCP, TTFB)
 * - Error tracking with stack traces
 * - Console log capture
 * - Session tracking
 * - Network request monitoring
 * - Custom events and measurements
 *
 * Configuration via environment variables:
 * - VITE_FARO_URL: Grafana Faro collector URL
 * - VITE_FARO_APP_NAME: Application name (default: missing-table-frontend)
 */

import {
  initializeFaro,
  getWebInstrumentations,
  LogLevel,
} from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';

// Singleton Faro instance
let faro = null;

/**
 * Initialize Grafana Faro
 * Call this at application startup (in main.js)
 */
export function initFaro() {
  // Skip if already initialized
  if (faro) {
    return faro;
  }

  const faroUrl = import.meta.env.VITE_FARO_URL;
  const appName =
    import.meta.env.VITE_FARO_APP_NAME || 'missing-table-frontend';
  const appVersion = import.meta.env.VITE_VERSION || '1.0.0';
  const environment = import.meta.env.MODE;

  // Check if Faro is configured
  if (!faroUrl) {
    console.log('[Faro] Not configured - VITE_FARO_URL not set');
    console.log('[Faro] Running in local-only mode (no data exported)');
    return null;
  }

  try {
    faro = initializeFaro({
      url: faroUrl,
      app: {
        name: appName,
        version: appVersion,
        environment: environment,
      },

      instrumentations: [
        // Web Vitals, errors, console logs, sessions
        ...getWebInstrumentations({
          captureConsole: true,
          captureConsoleDisabledLevels: [LogLevel.DEBUG, LogLevel.TRACE],
        }),
        // Distributed tracing
        new TracingInstrumentation(),
      ],

      // Session tracking
      sessionTracking: {
        enabled: true,
        persistent: true, // Persist session across page reloads
      },

      // Batch and send settings
      batching: {
        enabled: true,
        sendTimeout: 1000, // Send batch after 1 second
        itemLimit: 50, // Or when 50 items accumulated
      },
    });

    console.log(
      `[Faro] Initialized - ${appName} v${appVersion} (${environment})`
    );
    console.log(`[Faro] Collector: ${faroUrl}`);

    return faro;
  } catch (error) {
    console.error('[Faro] Failed to initialize:', error);
    return null;
  }
}

/**
 * Get the Faro instance
 */
export function getFaro() {
  return faro;
}

// =============================================================================
// HELPER FUNCTIONS - Compatible with old telemetry API
// =============================================================================

/**
 * Record a page view event
 * @param {string} pageName - Name of the page/tab
 * @param {Object} attributes - Additional attributes
 */
export function recordPageView(pageName, attributes = {}) {
  if (!faro) return;

  faro.api.pushEvent('page_view', {
    page_name: pageName,
    ...attributes,
  });
}

/**
 * Record a login event
 * @param {boolean} success - Whether login succeeded
 * @param {Object} attributes - Additional attributes
 */
export function recordLogin(success, attributes = {}) {
  if (!faro) return;

  faro.api.pushEvent('auth_login', {
    success: String(success),
    ...attributes,
  });

  // Also record as measurement for metrics
  faro.api.pushMeasurement({
    type: 'auth_login',
    values: {
      count: 1,
      success: success ? 1 : 0,
    },
  });
}

/**
 * Record login duration
 * @param {number} durationMs - Login duration in milliseconds
 * @param {boolean} success - Whether login succeeded
 */
export function recordLoginDuration(durationMs, success) {
  if (!faro) return;

  faro.api.pushMeasurement({
    type: 'auth_login_duration',
    values: {
      duration_ms: durationMs,
    },
    context: {
      success: String(success),
    },
  });
}

/**
 * Record a signup event
 * @param {boolean} success - Whether signup succeeded
 * @param {string} signupType - Type of signup
 * @param {Object} attributes - Additional attributes
 */
export function recordSignup(success, signupType = 'signup', attributes = {}) {
  if (!faro) return;

  faro.api.pushEvent('auth_signup', {
    success: String(success),
    signup_type: signupType,
    ...attributes,
  });
}

/**
 * Record a logout event
 */
export function recordLogout() {
  if (!faro) return;

  faro.api.pushEvent('auth_logout', {});
}

/**
 * Record an HTTP request
 * @param {string} endpoint - API endpoint path
 * @param {string} method - HTTP method
 * @param {number} statusCode - HTTP response status code
 * @param {number} durationMs - Request duration in milliseconds
 */
export function recordHttpRequest(endpoint, method, statusCode, durationMs) {
  if (!faro) return;

  // Normalize endpoint to avoid high cardinality
  const normalizedEndpoint = endpoint
    .replace(/\/\d+/g, '/:id')
    .replace(/\/[a-f0-9-]{36}/g, '/:uuid');

  faro.api.pushMeasurement({
    type: 'http_request',
    values: {
      duration_ms: durationMs,
      status_code: statusCode,
    },
    context: {
      endpoint: normalizedEndpoint,
      method: method.toUpperCase(),
      success: String(statusCode >= 200 && statusCode < 400),
    },
  });
}

/**
 * Record a frontend error
 * @param {string} errorType - Type of error
 * @param {Object} attributes - Additional attributes
 */
export function recordError(errorType, attributes = {}) {
  if (!faro) return;

  // Faro automatically captures errors, but we can also push custom ones
  faro.api.pushEvent('frontend_error', {
    error_type: errorType,
    ...attributes,
  });
}

/**
 * Record an invite request
 * @param {boolean} success - Whether request succeeded
 */
export function recordInviteRequest(success) {
  if (!faro) return;

  faro.api.pushEvent('invite_request', {
    success: String(success),
  });
}

/**
 * Record a session refresh
 * @param {boolean} success - Whether refresh succeeded
 */
export function recordSessionRefresh(success) {
  if (!faro) return;

  faro.api.pushEvent('session_refresh', {
    success: String(success),
  });
}

/**
 * Set user context for Faro (call after login)
 * @param {string} userId - User ID
 * @param {Object} attributes - Additional user attributes (role, etc.)
 */
export function setFaroUser(userId, attributes = {}) {
  if (!faro) return;

  faro.api.setUser({
    id: userId,
    attributes,
  });
}

/**
 * Clear user context for Faro (call on logout)
 */
export function clearFaroUser() {
  if (!faro) return;

  faro.api.resetUser();
}

/**
 * Get telemetry status for debugging
 */
export function getTelemetryStatus() {
  return {
    enabled: !!faro,
    faroUrl: import.meta.env.VITE_FARO_URL || 'not configured',
    appName: import.meta.env.VITE_FARO_APP_NAME || 'missing-table-frontend',
    environment: import.meta.env.MODE,
  };
}

// Expose global API for runtime debugging
if (typeof window !== 'undefined') {
  window.MT_TELEMETRY = {
    status: () => {
      const status = getTelemetryStatus();
      console.table(status);
      return status;
    },
    faro: () => faro,
  };
}
