/**
 * Telemetry Configuration and Toggle Management
 *
 * Provides environment variable defaults with runtime override capability.
 * Toggle state persists in localStorage for session continuity.
 */

const STORAGE_KEY = 'mt_telemetry_enabled';

/**
 * Get the current telemetry enabled state
 * Precedence: localStorage > environment variable > default (true)
 */
export function isTelemetryEnabled() {
  // Check localStorage for runtime override
  const storedValue = localStorage.getItem(STORAGE_KEY);
  if (storedValue !== null) {
    return storedValue === 'true';
  }

  // Fall back to environment variable
  const envValue = process.env.VUE_APP_TELEMETRY_ENABLED;
  if (envValue !== undefined) {
    return envValue === 'true';
  }

  // Default: enabled in production, disabled locally
  return process.env.NODE_ENV === 'production';
}

/**
 * Enable telemetry at runtime
 */
export function enableTelemetry() {
  localStorage.setItem(STORAGE_KEY, 'true');
  console.log('[MT Telemetry] Enabled - refresh page to apply');
}

/**
 * Disable telemetry at runtime
 */
export function disableTelemetry() {
  localStorage.setItem(STORAGE_KEY, 'false');
  console.log('[MT Telemetry] Disabled - refresh page to apply');
}

/**
 * Clear runtime override (revert to environment default)
 */
export function resetTelemetry() {
  localStorage.removeItem(STORAGE_KEY);
  console.log(
    '[MT Telemetry] Reset to environment default - refresh page to apply'
  );
}

/**
 * Get current telemetry status
 */
export function getTelemetryStatus() {
  const enabled = isTelemetryEnabled();
  const source =
    localStorage.getItem(STORAGE_KEY) !== null
      ? 'localStorage override'
      : process.env.VUE_APP_TELEMETRY_ENABLED !== undefined
        ? 'environment variable'
        : 'default';

  return {
    enabled,
    source,
    endpoint: process.env.VUE_APP_GRAFANA_OTLP_ENDPOINT || 'not configured',
    environment: process.env.VUE_APP_OTEL_ENVIRONMENT || process.env.NODE_ENV,
  };
}

/**
 * Get Grafana Cloud configuration
 */
export function getGrafanaConfig() {
  return {
    endpoint: process.env.VUE_APP_GRAFANA_OTLP_ENDPOINT,
    instanceId: process.env.VUE_APP_GRAFANA_INSTANCE_ID,
    apiKey: process.env.VUE_APP_GRAFANA_API_KEY,
    serviceName:
      process.env.VUE_APP_OTEL_SERVICE_NAME || 'missing-table-frontend',
    environment: process.env.VUE_APP_OTEL_ENVIRONMENT || process.env.NODE_ENV,
  };
}

/**
 * Check if Grafana Cloud is properly configured
 */
export function isGrafanaConfigured() {
  const config = getGrafanaConfig();
  return !!(config.endpoint && config.instanceId && config.apiKey);
}

// Expose global API for runtime control
if (typeof window !== 'undefined') {
  window.MT_TELEMETRY = {
    enable: enableTelemetry,
    disable: disableTelemetry,
    reset: resetTelemetry,
    status: () => {
      const status = getTelemetryStatus();
      console.table(status);
      return status;
    },
  };
}
