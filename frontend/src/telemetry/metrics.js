/**
 * Metric Definitions and Helper Functions
 *
 * Provides pre-defined metrics and safe recording functions
 * for the Missing Table frontend observability.
 */

import { getMeter } from './otel';
import { isTelemetryEnabled } from './config';

// Cached metric instruments
const metrics = {};

/**
 * Get or create a counter metric
 */
function getCounter(name, description, unit = '1') {
  if (!metrics[name]) {
    const meter = getMeter();
    if (meter) {
      metrics[name] = meter.createCounter(name, {
        description,
        unit,
      });
    }
  }
  return metrics[name];
}

/**
 * Get or create a histogram metric
 */
function getHistogram(name, description, unit = 'ms') {
  if (!metrics[name]) {
    const meter = getMeter();
    if (meter) {
      metrics[name] = meter.createHistogram(name, {
        description,
        unit,
      });
    }
  }
  return metrics[name];
}

/**
 * Safe wrapper for recording metrics
 * Catches errors to prevent telemetry failures from affecting the app
 */
function safeRecord(recordFn) {
  if (!isTelemetryEnabled()) {
    return;
  }

  try {
    recordFn();
  } catch (error) {
    console.warn('[MT Telemetry] Failed to record metric:', error.message);
  }
}

// =============================================================================
// PAGE VIEW METRICS
// =============================================================================

/**
 * Record a page view
 * @param {string} pageName - Name of the page/tab
 * @param {Object} attributes - Additional attributes
 */
export function recordPageView(pageName, attributes = {}) {
  safeRecord(() => {
    const counter = getCounter('page_view_total', 'Total number of page views');
    if (counter) {
      counter.add(1, {
        page_name: pageName,
        ...attributes,
      });
    }
  });
}

// =============================================================================
// AUTH METRICS
// =============================================================================

/**
 * Record a login attempt
 * @param {boolean} success - Whether login succeeded
 * @param {Object} attributes - Additional attributes (error_type, etc.)
 */
export function recordLogin(success, attributes = {}) {
  safeRecord(() => {
    const counter = getCounter(
      'auth_login_total',
      'Total number of login attempts'
    );
    if (counter) {
      counter.add(1, {
        status: success ? 'success' : 'failure',
        ...attributes,
      });
    }
  });
}

/**
 * Record login duration
 * @param {number} durationMs - Login duration in milliseconds
 * @param {boolean} success - Whether login succeeded
 */
export function recordLoginDuration(durationMs, success) {
  safeRecord(() => {
    const histogram = getHistogram(
      'auth_login_duration_ms',
      'Login operation duration in milliseconds'
    );
    if (histogram) {
      histogram.record(durationMs, {
        status: success ? 'success' : 'failure',
      });
    }
  });
}

/**
 * Record a signup attempt
 * @param {boolean} success - Whether signup succeeded
 * @param {string} signupType - Type of signup (signup, signup_with_invite)
 * @param {Object} attributes - Additional attributes
 */
export function recordSignup(success, signupType = 'signup', attributes = {}) {
  safeRecord(() => {
    const counter = getCounter(
      'auth_signup_total',
      'Total number of signup attempts'
    );
    if (counter) {
      counter.add(1, {
        status: success ? 'success' : 'failure',
        signup_type: signupType,
        ...attributes,
      });
    }
  });
}

/**
 * Record a logout
 */
export function recordLogout() {
  safeRecord(() => {
    const counter = getCounter('auth_logout_total', 'Total number of logouts');
    if (counter) {
      counter.add(1);
    }
  });
}

// =============================================================================
// HTTP REQUEST METRICS
// =============================================================================

/**
 * Record an HTTP request
 * @param {string} endpoint - API endpoint path
 * @param {string} method - HTTP method
 * @param {number} statusCode - HTTP response status code
 * @param {number} durationMs - Request duration in milliseconds
 */
export function recordHttpRequest(endpoint, method, statusCode, durationMs) {
  safeRecord(() => {
    // Counter for total requests
    const counter = getCounter(
      'http_request_total',
      'Total number of HTTP requests'
    );
    if (counter) {
      counter.add(1, {
        endpoint: normalizeEndpoint(endpoint),
        method: method.toUpperCase(),
        status_code: String(statusCode),
        success: statusCode >= 200 && statusCode < 400 ? 'true' : 'false',
      });
    }

    // Histogram for request duration
    const histogram = getHistogram(
      'http_request_duration_ms',
      'HTTP request duration in milliseconds'
    );
    if (histogram) {
      histogram.record(durationMs, {
        endpoint: normalizeEndpoint(endpoint),
        method: method.toUpperCase(),
        status_code: String(statusCode),
      });
    }
  });
}

/**
 * Normalize endpoint paths to avoid high cardinality
 * e.g., /api/teams/123 -> /api/teams/:id
 */
function normalizeEndpoint(endpoint) {
  return endpoint
    .replace(/\/\d+/g, '/:id')
    .replace(/\/[a-f0-9-]{36}/g, '/:uuid');
}

// =============================================================================
// ERROR METRICS
// =============================================================================

/**
 * Record a frontend error
 * @param {string} errorType - Type of error (js_error, network_error, etc.)
 * @param {Object} attributes - Additional attributes
 */
export function recordError(errorType, attributes = {}) {
  safeRecord(() => {
    const counter = getCounter(
      'frontend_error_total',
      'Total number of frontend errors'
    );
    if (counter) {
      counter.add(1, {
        error_type: errorType,
        ...attributes,
      });
    }
  });
}

// =============================================================================
// WEB VITALS METRICS
// =============================================================================

/**
 * Record a Web Vital metric
 * @param {string} name - Vital name (LCP, FID, CLS, FCP, TTFB)
 * @param {number} value - Metric value
 * @param {string} rating - Rating (good, needs-improvement, poor)
 */
export function recordWebVital(name, value, rating) {
  safeRecord(() => {
    const histogram = getHistogram(
      `web_vitals_${name.toLowerCase()}`,
      `Web Vital: ${name}`,
      name === 'CLS' ? '1' : 'ms'
    );
    if (histogram) {
      histogram.record(value, {
        rating,
      });
    }
  });
}

// =============================================================================
// BUSINESS METRICS
// =============================================================================

/**
 * Record an invite request
 * @param {boolean} success - Whether request succeeded
 */
export function recordInviteRequest(success) {
  safeRecord(() => {
    const counter = getCounter(
      'invite_request_total',
      'Total number of invite requests'
    );
    if (counter) {
      counter.add(1, {
        status: success ? 'success' : 'failure',
      });
    }
  });
}

/**
 * Record a session refresh
 * @param {boolean} success - Whether refresh succeeded
 */
export function recordSessionRefresh(success) {
  safeRecord(() => {
    const counter = getCounter(
      'session_refresh_total',
      'Total number of session refreshes'
    );
    if (counter) {
      counter.add(1, {
        status: success ? 'success' : 'failure',
      });
    }
  });
}
