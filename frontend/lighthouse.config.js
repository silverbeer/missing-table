// Lighthouse CI Configuration for Performance Budget Validation

module.exports = {
  ci: {
    collect: {
      numberOfRuns: 3,
      startServerCommand: 'npm run serve',
      startServerReadyPattern: 'Local:',
      startServerReadyTimeout: 30000,
      url: [
        'http://localhost:8080',
        'http://localhost:8080/standings',
        'http://localhost:8080/schedule',
      ],
      settings: {
        chromeFlags: '--no-sandbox --disable-dev-shm-usage',
        preset: 'desktop',
        onlyCategories: [
          'performance',
          'accessibility',
          'best-practices',
          'seo',
        ],
        skipAudits: ['uses-http2', 'canonical', 'structured-data'],
      },
    },
    assert: {
      preset: 'lighthouse:recommended',
      assertions: {
        // Performance Budget
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:accessibility': ['error', { minScore: 0.95 }],
        'categories:best-practices': ['error', { minScore: 0.95 }],
        'categories:seo': ['error', { minScore: 0.9 }],

        // Core Web Vitals
        'largest-contentful-paint': ['error', { maxNumericValue: 2500 }],
        'first-input-delay': ['error', { maxNumericValue: 100 }],
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.1 }],
        'first-contentful-paint': ['error', { maxNumericValue: 1500 }],

        // Resource Budget
        'total-byte-weight': ['warn', { maxNumericValue: 3145728 }], // 3MB
        'dom-size': ['warn', { maxNumericValue: 1500 }],
        'uses-optimized-images': 'error',
        'uses-webp-images': 'warn',
        'uses-responsive-images': 'error',

        // JavaScript Budget
        'unminified-javascript': 'error',
        'unused-javascript': ['warn', { maxNumericValue: 204800 }], // 200KB
        'legacy-javascript': 'error',

        // CSS Budget
        'unminified-css': 'error',
        'unused-css-rules': ['warn', { maxNumericValue: 51200 }], // 50KB

        // Security
        'is-on-https': 'error',
        'uses-http2': 'warn',
        'no-vulnerable-libraries': 'error',

        // Best Practices
        'errors-in-console': 'warn',
        'image-aspect-ratio': 'error',
        'image-size-responsive': 'error',

        // Accessibility
        'color-contrast': 'error',
        'heading-order': 'error',
        'link-name': 'error',
        'button-name': 'error',
        'image-alt': 'error',
        label: 'error',

        // SEO
        'meta-description': 'error',
        'document-title': 'error',
        'meta-viewport': 'error',
        'font-size': 'error',
      },
    },
    upload: {
      target: 'temporary-public-storage',
      githubAppToken: process.env.LHCI_GITHUB_APP_TOKEN || undefined,
      githubToken: process.env.GITHUB_TOKEN || undefined,
    },
    server: {
      port: 9001,
      storage: {
        storageMethod: 'sql',
        sqlDialect: 'sqlite',
        sqlDatabasePath: './lhci.db',
      },
    },
    wizard: {
      targetDir: './lighthouse-reports',
    },
  },
};
