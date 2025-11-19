/**
 * Frontend Security Monitoring for Missing Table Application
 *
 * This module provides comprehensive client-side security monitoring including:
 * - XSS attempt detection and reporting
 * - Content Security Policy violation tracking
 * - Error monitoring for security issues
 * - User behavior analytics for anomaly detection
 */

import { getApiBaseUrl } from '../config/api';

class SecurityMonitor {
  constructor() {
    this.apiUrl = getApiBaseUrl();
    this.sessionId = this.generateSessionId();
    this.eventQueue = [];
    this.userBehavior = {
      pageViews: [],
      clicks: [],
      errors: [],
      suspiciousActivities: [],
    };
    this.enabled = false;
    this.initialized = false;
  }

  enable() {
    if (!this.enabled) {
      this.enabled = true;
      if (!this.initialized) {
        this.init();
        this.initialized = true;
      }
    }
  }

  disable() {
    this.enabled = false;
  }

  init() {
    this.setupCSPViolationReporting();
    this.setupErrorMonitoring();
    this.setupXSSDetection();
    this.setupUserBehaviorTracking();
    this.setupPerformanceMonitoring();

    // Send queued events periodically
    setInterval(() => this.flushEventQueue(), 30000); // Every 30 seconds

    // Send events before page unload
    window.addEventListener('beforeunload', () => this.flushEventQueue());
  }

  generateSessionId() {
    return (
      'session_' + Date.now() + '_' + Math.random().toString(36).substring(2)
    );
  }

  setupCSPViolationReporting() {
    document.addEventListener('securitypolicyviolation', event => {
      this.reportSecurityEvent({
        type: 'csp_violation',
        severity: 'high',
        details: {
          violatedDirective: event.violatedDirective,
          blockedURI: event.blockedURI,
          sourceFile: event.sourceFile,
          lineNumber: event.lineNumber,
          columnNumber: event.columnNumber,
          originalPolicy: event.originalPolicy,
        },
      });
    });
  }

  setupErrorMonitoring() {
    // Global error handler
    window.addEventListener('error', event => {
      this.analyzeError(event.error, {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        type: 'javascript_error',
      });
    });

    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', event => {
      this.analyzeError(event.reason, {
        type: 'unhandled_promise_rejection',
        promise: event.promise,
      });
    });

    // Vue error handler (if available)
    if (window.Vue && window.Vue.config) {
      const originalErrorHandler = window.Vue.config.errorHandler;
      window.Vue.config.errorHandler = (err, vm, info) => {
        this.analyzeError(err, {
          type: 'vue_error',
          componentInfo: info,
          vueComponent: vm?.$options?.name || 'Unknown',
        });

        if (originalErrorHandler) {
          originalErrorHandler(err, vm, info);
        }
      };
    }
  }

  setupXSSDetection() {
    // Monitor for potential XSS attempts
    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              this.scanElementForXSS(node);
            }
          });
        }

        if (mutation.type === 'attributes') {
          this.scanAttributeForXSS(mutation.target, mutation.attributeName);
        }
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['onclick', 'onload', 'onerror', 'src', 'href'],
    });

    // Monitor for suspicious eval usage
    const originalEval = window.eval;
    window.eval = (...args) => {
      this.reportSecurityEvent({
        type: 'suspicious_eval',
        severity: 'critical',
        details: {
          code: args[0]?.substring(0, 200), // First 200 chars
          stackTrace: new Error().stack,
        },
      });
      return originalEval.apply(this, args);
    };
  }

  scanElementForXSS(element) {
    const dangerousPatterns = [
      /javascript:/i,
      /vbscript:/i,
      /data:text\/html/i,
      /on\w+\s*=/i,
      /<script/i,
      /<iframe/i,
      /<object/i,
      /<embed/i,
    ];

    const innerHTML = element.innerHTML;
    const outerHTML = element.outerHTML;

    dangerousPatterns.forEach(pattern => {
      if (pattern.test(innerHTML) || pattern.test(outerHTML)) {
        this.reportSecurityEvent({
          type: 'xss_attempt',
          severity: 'critical',
          details: {
            pattern: pattern.toString(),
            elementTag: element.tagName,
            elementId: element.id,
            elementClass: element.className,
            innerHTML: innerHTML.substring(0, 500),
            location: window.location.href,
          },
        });
      }
    });
  }

  scanAttributeForXSS(element, attributeName) {
    if (!attributeName) return;

    const attributeValue = element.getAttribute(attributeName);
    if (!attributeValue) return;

    const dangerousPatterns = [
      /javascript:/i,
      /vbscript:/i,
      /data:text\/html/i,
    ];

    dangerousPatterns.forEach(pattern => {
      if (pattern.test(attributeValue)) {
        this.reportSecurityEvent({
          type: 'xss_attempt',
          severity: 'critical',
          details: {
            pattern: pattern.toString(),
            attribute: attributeName,
            value: attributeValue,
            elementTag: element.tagName,
            elementId: element.id,
            location: window.location.href,
          },
        });
      }
    });
  }

  setupUserBehaviorTracking() {
    // Track page views
    this.trackPageView();

    // Track navigation
    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = (...args) => {
      this.trackPageView();
      return originalPushState.apply(history, args);
    };

    history.replaceState = (...args) => {
      this.trackPageView();
      return originalReplaceState.apply(history, args);
    };

    window.addEventListener('popstate', () => {
      this.trackPageView();
    });

    // Track clicks for suspicious patterns
    document.addEventListener('click', event => {
      this.trackClick(event);
    });

    // Track form submissions
    document.addEventListener('submit', event => {
      this.trackFormSubmission(event);
    });

    // Track rapid/suspicious input patterns
    document.addEventListener('input', event => {
      this.trackInput(event);
    });
  }

  setupPerformanceMonitoring() {
    // Monitor for performance anomalies that might indicate attacks
    if ('PerformanceObserver' in window) {
      // Long tasks that might indicate code injection
      const longTaskObserver = new PerformanceObserver(list => {
        list.getEntries().forEach(entry => {
          if (entry.duration > 1000) {
            // Tasks longer than 1 second
            this.reportSecurityEvent({
              type: 'suspicious_performance',
              severity: 'medium',
              details: {
                duration: entry.duration,
                startTime: entry.startTime,
                name: entry.name,
                type: 'long_task',
              },
            });
          }
        });
      });

      longTaskObserver.observe({ entryTypes: ['longtask'] });

      // Monitor for excessive resource loading
      const resourceObserver = new PerformanceObserver(list => {
        const entries = list.getEntries();
        const externalResources = entries.filter(
          entry => !entry.name.startsWith(window.location.origin)
        );

        if (externalResources.length > 10) {
          // More than 10 external resources
          this.reportSecurityEvent({
            type: 'suspicious_resource_loading',
            severity: 'medium',
            details: {
              externalResourceCount: externalResources.length,
              resources: externalResources.map(r => r.name).slice(0, 5),
            },
          });
        }
      });

      resourceObserver.observe({ entryTypes: ['resource'] });
    }
  }

  trackPageView() {
    const pageView = {
      url: window.location.href,
      timestamp: Date.now(),
      referrer: document.referrer,
      userAgent: navigator.userAgent,
    };

    this.userBehavior.pageViews.push(pageView);

    // Keep only last 50 page views
    if (this.userBehavior.pageViews.length > 50) {
      this.userBehavior.pageViews.shift();
    }

    // Detect suspicious navigation patterns
    this.analyzeNavigationPatterns();
  }

  trackClick(event) {
    const click = {
      timestamp: Date.now(),
      target: {
        tagName: event.target.tagName,
        id: event.target.id,
        className: event.target.className,
        text: event.target.textContent?.substring(0, 100),
      },
      coordinates: {
        x: event.clientX,
        y: event.clientY,
      },
    };

    this.userBehavior.clicks.push(click);

    // Keep only last 100 clicks
    if (this.userBehavior.clicks.length > 100) {
      this.userBehavior.clicks.shift();
    }

    // Detect click bombing or automated clicking
    this.analyzeClickPatterns();
  }

  trackFormSubmission(event) {
    const form = event.target;
    const formData = new FormData(form);

    // Check for potential injection attempts in form data
    for (let [key, value] of formData.entries()) {
      if (typeof value === 'string') {
        this.analyzeInputForThreats(value, key, 'form_submission');
      }
    }
  }

  trackInput(event) {
    const value = event.target.value;
    const inputName = event.target.name || event.target.id || 'unknown';

    // Analyze input for threats
    this.analyzeInputForThreats(value, inputName, 'user_input');
  }

  analyzeInputForThreats(input, fieldName, context) {
    if (!input || typeof input !== 'string') return;

    // XSS patterns
    const xssPatterns = [
      /<script[\s\S]*?>[\s\S]*?<\/script>/gi,
      /<iframe[\s\S]*?>[\s\S]*?<\/iframe>/gi,
      /javascript:/gi,
      /on\w+\s*=/gi,
      /<img[^>]*onerror/gi,
      /<svg[^>]*onload/gi,
    ];

    // SQL injection patterns
    const sqlPatterns = [
      /(\bUNION\b.*\bSELECT\b)/gi,
      /(\bOR\b.*[=<>].*[0-9])/gi,
      /('.*--)/gi,
      /(;.*DROP\b)/gi,
      /(;.*DELETE\b)/gi,
    ];

    // Check XSS patterns
    xssPatterns.forEach(pattern => {
      if (pattern.test(input)) {
        this.reportSecurityEvent({
          type: 'xss_attempt',
          severity: 'high',
          details: {
            fieldName,
            context,
            pattern: pattern.toString(),
            input: input.substring(0, 200),
            location: window.location.href,
          },
        });
      }
    });

    // Check SQL injection patterns
    sqlPatterns.forEach(pattern => {
      if (pattern.test(input)) {
        this.reportSecurityEvent({
          type: 'sql_injection_attempt',
          severity: 'critical',
          details: {
            fieldName,
            context,
            pattern: pattern.toString(),
            input: input.substring(0, 200),
            location: window.location.href,
          },
        });
      }
    });
  }

  analyzeNavigationPatterns() {
    const recentViews = this.userBehavior.pageViews.slice(-10);

    // Detect rapid page navigation (potential bot)
    if (recentViews.length >= 5) {
      const timeDiffs = [];
      for (let i = 1; i < recentViews.length; i++) {
        timeDiffs.push(recentViews[i].timestamp - recentViews[i - 1].timestamp);
      }

      const avgTimeDiff =
        timeDiffs.reduce((a, b) => a + b, 0) / timeDiffs.length;

      if (avgTimeDiff < 500) {
        // Less than 500ms between page views
        this.reportSecurityEvent({
          type: 'suspicious_navigation',
          severity: 'medium',
          details: {
            averageTimeBetweenViews: avgTimeDiff,
            recentViewCount: recentViews.length,
            pattern: 'rapid_navigation',
          },
        });
      }
    }
  }

  analyzeClickPatterns() {
    const recentClicks = this.userBehavior.clicks.slice(-20);

    if (recentClicks.length >= 10) {
      // Check for click bombing
      const now = Date.now();
      const clicksInLastSecond = recentClicks.filter(
        click => now - click.timestamp < 1000
      ).length;

      if (clicksInLastSecond > 5) {
        this.reportSecurityEvent({
          type: 'click_bombing',
          severity: 'medium',
          details: {
            clicksInLastSecond,
            totalRecentClicks: recentClicks.length,
          },
        });
      }

      // Check for robotic click patterns (same coordinates)
      const coordinates = recentClicks.map(
        c => `${c.coordinates.x},${c.coordinates.y}`
      );
      const uniqueCoordinates = new Set(coordinates);

      if (uniqueCoordinates.size === 1 && recentClicks.length > 5) {
        this.reportSecurityEvent({
          type: 'robotic_clicking',
          severity: 'medium',
          details: {
            clickCount: recentClicks.length,
            coordinates: Array.from(uniqueCoordinates)[0],
          },
        });
      }
    }
  }

  analyzeError(error, context) {
    const errorInfo = {
      message: error?.message || 'Unknown error',
      stack: error?.stack,
      timestamp: Date.now(),
      context,
    };

    this.userBehavior.errors.push(errorInfo);

    // Keep only last 50 errors
    if (this.userBehavior.errors.length > 50) {
      this.userBehavior.errors.shift();
    }

    // Check for security-related errors
    const securityKeywords = [
      'blocked by content security policy',
      'unsafe-eval',
      'unsafe-inline',
      'script-src',
      'object-src',
      'frame-src',
      'mixed content',
      'cors',
      'cross-origin',
    ];

    const errorText = (
      errorInfo.message +
      ' ' +
      (errorInfo.stack || '')
    ).toLowerCase();

    securityKeywords.forEach(keyword => {
      if (errorText.includes(keyword)) {
        this.reportSecurityEvent({
          type: 'security_error',
          severity: 'medium',
          details: {
            keyword,
            error: errorInfo,
            context,
          },
        });
      }
    });

    // Check for excessive errors (possible attack)
    const recentErrors = this.userBehavior.errors.filter(
      e => Date.now() - e.timestamp < 60000 // Last minute
    );

    if (recentErrors.length > 10) {
      this.reportSecurityEvent({
        type: 'excessive_errors',
        severity: 'medium',
        details: {
          errorCount: recentErrors.length,
          timeWindow: '1_minute',
        },
      });
    }
  }

  reportSecurityEvent(event) {
    if (!this.enabled) return;

    const securityEvent = {
      ...event,
      sessionId: this.sessionId,
      timestamp: Date.now(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      referrer: document.referrer,
      viewportSize: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
    };

    this.eventQueue.push(securityEvent);

    // Immediately send critical events
    if (event.severity === 'critical') {
      this.flushEventQueue();
    }

    console.warn('Security event detected:', securityEvent);
  }

  async flushEventQueue() {
    if (!this.enabled || this.eventQueue.length === 0) return;

    const events = [...this.eventQueue];
    this.eventQueue = [];

    try {
      await fetch(`${this.apiUrl}/api/security/client-events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          events,
          sessionId: this.sessionId,
          userBehaviorSummary: this.getUserBehaviorSummary(),
        }),
        credentials: 'include',
      });
    } catch (error) {
      console.error('Failed to send security events:', error);
      // Re-queue events for next attempt (keep only last 100)
      this.eventQueue = [...events, ...this.eventQueue].slice(-100);
    }
  }

  getUserBehaviorSummary() {
    return {
      pageViewCount: this.userBehavior.pageViews.length,
      clickCount: this.userBehavior.clicks.length,
      errorCount: this.userBehavior.errors.length,
      sessionDuration:
        Date.now() - (this.userBehavior.pageViews[0]?.timestamp || Date.now()),
      uniquePages: new Set(this.userBehavior.pageViews.map(pv => pv.url)).size,
    };
  }

  // Public API for manual reporting
  reportCustomEvent(type, severity, details) {
    this.reportSecurityEvent({
      type: `custom_${type}`,
      severity,
      details,
    });
  }

  // Get current session security status
  getSessionStatus() {
    return {
      sessionId: this.sessionId,
      eventCount: this.eventQueue.length,
      userBehavior: this.getUserBehaviorSummary(),
      isActive: true,
    };
  }
}

// Create and export global instance
const securityMonitor = new SecurityMonitor();

export default securityMonitor;
