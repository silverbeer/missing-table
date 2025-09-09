import { createApp } from 'vue';
import App from './App.vue';
import './style.css';

const app = createApp(App);

// Conditionally load security plugin
const DISABLE_SECURITY = process.env.VUE_APP_DISABLE_SECURITY === 'true';

if (!DISABLE_SECURITY) {
  import('./plugins/security.js').then(SecurityPlugin => {
    app.use(SecurityPlugin.default, {
      csp: true, // Enable Content Security Policy
      performanceMonitoring: true, // Enable Vue performance monitoring
    });
  });
}

app.mount('#app');
