/**
 * OpenTelemetry SDK Initialization
 *
 * Initializes OTEL metrics and tracing with Grafana Cloud export.
 * Must be imported before any other app code in main.js.
 */

import { resourceFromAttributes } from '@opentelemetry/resources';
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_DEPLOYMENT_ENVIRONMENT,
} from '@opentelemetry/semantic-conventions';
import {
  MeterProvider,
  PeriodicExportingMetricReader,
} from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import {
  isTelemetryEnabled,
  isGrafanaConfigured,
  getGrafanaConfig,
  getTelemetryStatus,
} from './config';

// Singleton instances
let meterProvider = null;
let meter = null;
let initialized = false;

/**
 * Initialize OpenTelemetry SDK
 */
export function initializeTelemetry() {
  if (initialized) {
    return;
  }

  // Check if telemetry is enabled
  if (!isTelemetryEnabled()) {
    console.log('[MT Telemetry] Disabled - skipping initialization');
    initialized = true;
    return;
  }

  // Check if Grafana is configured
  if (!isGrafanaConfigured()) {
    console.warn(
      '[MT Telemetry] Grafana Cloud not configured - metrics will not be exported'
    );
    // Still initialize with console exporter for local debugging
    initializeLocalOnly();
    initialized = true;
    return;
  }

  try {
    const config = getGrafanaConfig();

    // Create resource with service metadata
    const resource = resourceFromAttributes({
      [ATTR_SERVICE_NAME]: config.serviceName,
      [ATTR_SERVICE_VERSION]: process.env.VUE_APP_VERSION || '1.0.0',
      [ATTR_DEPLOYMENT_ENVIRONMENT]: config.environment,
    });

    // Create OTLP exporter for Grafana Cloud
    const metricExporter = new OTLPMetricExporter({
      url: `${config.endpoint}/v1/metrics`,
      headers: {
        Authorization: `Basic ${btoa(`${config.instanceId}:${config.apiKey}`)}`,
      },
    });

    // Create metric reader with periodic export (every 60 seconds)
    const metricReader = new PeriodicExportingMetricReader({
      exporter: metricExporter,
      exportIntervalMillis: 60000, // Export every 60 seconds
    });

    // Create meter provider
    meterProvider = new MeterProvider({
      resource,
      readers: [metricReader],
    });

    // Get meter instance
    meter = meterProvider.getMeter(config.serviceName);

    console.log('[MT Telemetry] Initialized with Grafana Cloud export');
    const status = getTelemetryStatus();
    console.log(`[MT Telemetry] Endpoint: ${status.endpoint}`);

    initialized = true;
  } catch (error) {
    console.error('[MT Telemetry] Failed to initialize:', error);
    // Fall back to local-only mode
    initializeLocalOnly();
    initialized = true;
  }
}

/**
 * Initialize local-only telemetry (no export)
 * Used when Grafana is not configured or initialization fails
 */
function initializeLocalOnly() {
  const config = getGrafanaConfig();

  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: config.serviceName,
    [ATTR_SERVICE_VERSION]: process.env.VUE_APP_VERSION || '1.0.0',
    [ATTR_DEPLOYMENT_ENVIRONMENT]: config.environment,
  });

  meterProvider = new MeterProvider({
    resource,
  });

  meter = meterProvider.getMeter(config.serviceName);

  console.log('[MT Telemetry] Initialized in local-only mode (no export)');
}

/**
 * Get the meter instance for creating metrics
 * @returns {import('@opentelemetry/api').Meter | null}
 */
export function getMeter() {
  if (!initialized) {
    initializeTelemetry();
  }
  return meter;
}

/**
 * Get the meter provider instance
 * @returns {MeterProvider | null}
 */
export function getMeterProvider() {
  return meterProvider;
}

/**
 * Shutdown telemetry gracefully
 */
export async function shutdownTelemetry() {
  if (meterProvider) {
    try {
      await meterProvider.shutdown();
      console.log('[MT Telemetry] Shutdown complete');
    } catch (error) {
      console.error('[MT Telemetry] Shutdown error:', error);
    }
  }
}

// Auto-initialize when module is imported
initializeTelemetry();

// Graceful shutdown on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    shutdownTelemetry();
  });
}
