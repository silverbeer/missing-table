<template>
  <footer class="version-footer">
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

      <!-- Status indicator (right side) -->
      <div class="status-indicator">
        <span
          v-if="status === 'healthy'"
          class="status-dot status-healthy"
        ></span>
        <span v-else class="status-dot status-error"></span>
        <span class="status-text">{{ status }}</span>
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

    // Determine environment based on current hostname
    const determineEnvironment = () => {
      const hostname = window.location.hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'local';
      } else if (hostname === 'dev.missingtable.com') {
        return 'dev';
      } else if (hostname === 'missingtable.com' || hostname === 'www.missingtable.com') {
        return 'production';
      }
      return 'unknown';
    };

    const fetchVersion = async () => {
      try {
        // Use relative URL - works with ingress routing on same domain
        const response = await fetch('/api/version');

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

    onMounted(() => {
      fetchVersion();
    });

    return {
      version,
      environment,
      status,
      currentYear,
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

.status-error {
  background-color: #dc3545;
  box-shadow: 0 0 4px rgba(220, 53, 69, 0.5);
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
