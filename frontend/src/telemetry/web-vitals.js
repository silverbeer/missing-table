/**
 * Web Vitals Integration
 *
 * Captures Core Web Vitals and reports them as OTEL metrics.
 * - LCP (Largest Contentful Paint)
 * - INP (Interaction to Next Paint) - replaced FID in 2024
 * - CLS (Cumulative Layout Shift)
 * - FCP (First Contentful Paint)
 * - TTFB (Time to First Byte)
 */

import { onLCP, onINP, onCLS, onFCP, onTTFB } from 'web-vitals';
import { recordWebVital } from './metrics';
import { isTelemetryEnabled } from './config';

/**
 * Initialize Web Vitals tracking
 * Call this after the app is mounted
 */
export function initWebVitals() {
  if (!isTelemetryEnabled()) {
    return;
  }

  // Report each vital when it becomes available
  // Note: FID was replaced by INP (Interaction to Next Paint) in web-vitals v4+
  onLCP(handleVital);
  onINP(handleVital);
  onCLS(handleVital);
  onFCP(handleVital);
  onTTFB(handleVital);

  console.log('[MT Telemetry] Web Vitals tracking initialized');
}

/**
 * Handle a Web Vital report
 * @param {Object} metric - Web Vital metric object
 */
function handleVital(metric) {
  const { name, value, rating } = metric;

  // Record to OTEL
  recordWebVital(name, value, rating);

  // Log for debugging in development
  if (process.env.NODE_ENV === 'development') {
    console.log(`[Web Vital] ${name}: ${value.toFixed(2)} (${rating})`);
  }
}

/**
 * Get Web Vitals thresholds for reference
 * These are the thresholds used by Google for "good" ratings
 */
export const WEB_VITALS_THRESHOLDS = {
  LCP: {
    good: 2500, // ms
    poor: 4000, // ms
    unit: 'ms',
    description: 'Largest Contentful Paint - measures loading performance',
  },
  INP: {
    good: 200, // ms
    poor: 500, // ms
    unit: 'ms',
    description: 'Interaction to Next Paint - measures interactivity',
  },
  CLS: {
    good: 0.1, // score
    poor: 0.25, // score
    unit: 'score',
    description: 'Cumulative Layout Shift - measures visual stability',
  },
  FCP: {
    good: 1800, // ms
    poor: 3000, // ms
    unit: 'ms',
    description: 'First Contentful Paint - measures initial render time',
  },
  TTFB: {
    good: 800, // ms
    poor: 1800, // ms
    unit: 'ms',
    description: 'Time to First Byte - measures server response time',
  },
};
