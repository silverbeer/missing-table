/**
 * Telemetry Module - Main Entry Point
 *
 * Import this module at the start of your application
 * to initialize OpenTelemetry with Grafana Cloud export.
 */

// Initialize OTEL SDK (must be first)
export { initializeTelemetry, getMeter, shutdownTelemetry } from './otel';

// Configuration and toggle management
export {
  isTelemetryEnabled,
  enableTelemetry,
  disableTelemetry,
  resetTelemetry,
  getTelemetryStatus,
  getGrafanaConfig,
  isGrafanaConfigured,
} from './config';

// Metric recording functions
export {
  recordPageView,
  recordLogin,
  recordLoginDuration,
  recordSignup,
  recordLogout,
  recordHttpRequest,
  recordError,
  recordWebVital,
  recordInviteRequest,
  recordSessionRefresh,
} from './metrics';

// Web Vitals integration
export { initWebVitals, WEB_VITALS_THRESHOLDS } from './web-vitals';
