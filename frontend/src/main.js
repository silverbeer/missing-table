// Initialize telemetry first (before any other app code)
import './telemetry';
import { initWebVitals } from './telemetry';

import { createApp } from 'vue';
import App from './App.vue';
import './style.css';

const app = createApp(App);

// Initialize Web Vitals tracking after app creation
initWebVitals();

// Conditionally load security plugin
const DISABLE_SECURITY = import.meta.env.VITE_DISABLE_SECURITY === 'true';

if (!DISABLE_SECURITY) {
  import('./plugins/security.js').then(SecurityPlugin => {
    app.use(SecurityPlugin.default, {
      csp: true, // Enable Content Security Policy
      performanceMonitoring: true, // Enable Vue performance monitoring
    });
  });
}

app.mount('#app');
