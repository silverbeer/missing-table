<template>
  <footer class="version-footer">
    <!-- Error banner (teleported to body) -->
    <Teleport to="body">
      <div
        v-if="status === 'error' && !errorDismissed"
        class="fixed top-0 inset-x-0 z-50 bg-red-900 text-white text-sm px-4 py-2 flex items-center justify-between gap-4"
        data-testid="api-error-banner"
      >
        <span
          >⚠ Could not reach the API server — some features may be
          unavailable.</span
        >
        <div class="flex items-center gap-3 shrink-0">
          <button
            @click="retryFetch"
            class="underline hover:no-underline font-medium"
          >
            Retry
          </button>
          <button
            @click="errorDismissed = true"
            class="font-bold hover:opacity-75"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      </div>
    </Teleport>

    <div class="version-container">
      <!-- Version info (left side) -->
      <div class="version-info">
        <span v-if="version" class="version-text">
          {{ version }}
          <span v-if="environment !== 'production'" class="environment-badge">
            {{ environment }}
          </span>
        </span>
        <span v-else class="version-loading">Loading version...</span>
      </div>

      <!-- Copyright/branding (center) -->
      <div class="copyright">© {{ currentYear }} Missing Table</div>

      <!-- Status indicator (right side) — only show when healthy -->
      <div class="status-indicator">
        <template v-if="status === 'healthy'">
          <span class="status-dot status-healthy"></span>
          <span class="status-text">Healthy</span>
        </template>
      </div>
    </div>
  </footer>
</template>

<script>
import { ref, onMounted, computed } from 'vue';

export default {
  name: 'VersionFooter',
  setup() {
    const version = ref(null);
    const environment = ref('unknown');
    const status = ref('healthy');
    const currentYear = computed(() => new Date().getFullYear());
    const errorDismissed = ref(false);

    // Determine environment based on current hostname
    const determineEnvironment = () => {
      const hostname = window.location.hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'local';
      } else if (hostname === 'dev.missingtable.com') {
        return 'dev';
      } else if (
        hostname === 'missingtable.com' ||
        hostname === 'www.missingtable.com'
      ) {
        return 'production';
      }
      return 'unknown';
    };

    const fetchVersion = async () => {
      errorDismissed.value = false;
      try {
        const apiBase =
          window.location.hostname === 'localhost' ||
          window.location.hostname === '127.0.0.1'
            ? 'http://localhost:8000'
            : '';
        const response = await fetch(`${apiBase}/api/version`);

        if (response.ok) {
          const data = await response.json();
          version.value = data.version;
          status.value = data.status;
          // Set environment based on hostname, not API response
          environment.value = determineEnvironment();
        } else {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
      } catch (error) {
        console.warn('Failed to fetch version info:', error);
        version.value = 'Unknown';
        status.value = 'error';
        // Still set environment based on hostname even if API fails
        environment.value = determineEnvironment();
      }
    };

    const retryFetch = () => {
      errorDismissed.value = false;
      fetchVersion();
    };

    onMounted(() => {
      fetchVersion();
    });

    return {
      version,
      environment,
      status,
      currentYear,
      errorDismissed,
      fetchVersion,
      retryFetch,
    };
  },
};
</script>

<style scoped>
.version-footer {
  background-color: #f8f9fa;
  border-top: 1px solid #e0e0e0;
  padding: 0.75rem 1rem;
  margin-top: 2rem;
  font-size: 0.875rem;
  color: #6c757d;
}

.version-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.version-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.version-text {
  font-family: 'Courier New', monospace;
  font-size: 0.8125rem;
  color: #495057;
}

.version-loading {
  color: #adb5bd;
  font-style: italic;
}

.environment-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  background-color: #ffc107;
  color: #212529;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  margin-left: 0.5rem;
}

.environment-badge.dev {
  background-color: #17a2b8;
  color: white;
}

.copyright {
  text-align: center;
  flex: 1;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-healthy {
  background-color: #28a745;
  box-shadow: 0 0 4px rgba(40, 167, 69, 0.5);
}

.status-text {
  font-size: 0.75rem;
  color: #6c757d;
  text-transform: capitalize;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .version-container {
    flex-direction: column;
    text-align: center;
    gap: 0.5rem;
  }

  .copyright {
    order: -1;
  }

  .version-info,
  .status-indicator {
    justify-content: center;
  }
}
</style>
