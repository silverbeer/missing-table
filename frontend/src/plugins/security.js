/**
 * Vue 3 Security Plugin
 *
 * Integrates client-side security monitoring with Vue.js application
 */

import securityMonitor from '../utils/security-monitor.js';
import { getApiBaseUrl } from '../config/api';

const SecurityPlugin = {
  install(app, options = {}) {
    // Enable the security monitor
    securityMonitor.enable();

    // Make security monitor available globally
    app.config.globalProperties.$security = securityMonitor;
    app.provide('security', securityMonitor);

    // Set up Vue-specific error handling
    const originalErrorHandler = app.config.errorHandler;
    app.config.errorHandler = (err, instance, info) => {
      // Report Vue errors to security monitor
      securityMonitor.reportCustomEvent('vue_error', 'medium', {
        error: {
          message: err.message,
          stack: err.stack,
          name: err.name,
        },
        componentInfo: info,
        componentName:
          instance?.$options?.name || instance?.$?.type?.name || 'Unknown',
        location: window.location.href,
      });

      // Call original handler if it exists
      if (originalErrorHandler) {
        originalErrorHandler(err, instance, info);
      } else {
        console.error('Vue Error:', err, info);
      }
    };

    // Set up Content Security Policy headers monitoring
    if (options.csp !== false) {
      this.setupCSPHeaders();
    }

    // Set up performance monitoring for Vue components
    if (options.performanceMonitoring !== false) {
      this.setupVuePerformanceMonitoring(app);
    }
  },

  setupCSPHeaders() {
    // Add CSP meta tag if not present
    if (!document.querySelector('meta[http-equiv="Content-Security-Policy"]')) {
      const cspMeta = document.createElement('meta');
      cspMeta.setAttribute('http-equiv', 'Content-Security-Policy');
      cspMeta.setAttribute('content', this.getCSPPolicy());
      document.head.appendChild(cspMeta);
    }
  },

  getCSPPolicy() {
    // Define a strict CSP policy
    // Use runtime API detection
    const apiUrl = getApiBaseUrl();

    const policy = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: https:",
      `connect-src 'self' ${apiUrl} https://api.github.com ws: wss:`,
      "frame-src 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      'block-all-mixed-content',
      'upgrade-insecure-requests',
    ].join('; ');

    return policy;
  },

  setupVuePerformanceMonitoring(app) {
    // Monitor component render times
    const originalMount = app.mount;
    app.mount = function (...args) {
      const start = performance.now();
      const result = originalMount.apply(this, args);
      const duration = performance.now() - start;

      if (duration > 1000) {
        // Slow mount (> 1 second)
        securityMonitor.reportCustomEvent('slow_component_mount', 'low', {
          duration,
          component: 'app_root',
          type: 'mount_performance',
        });
      }

      return result;
    };
  },
};

export default SecurityPlugin;
