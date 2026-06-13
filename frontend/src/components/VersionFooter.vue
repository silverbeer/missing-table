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
      <!-- Version info (left side) — internal info, members only -->
      <div class="version-info">
        <template v-if="authStore.isAuthenticated.value">
          <template v-if="version">
            <button
              type="button"
              class="version-text version-button"
              title="What's New"
              data-testid="whats-new-trigger"
              @click="$emit('open-whats-new')"
            >
              {{ version }}
            </button>
            <span v-if="environment !== 'production'" class="environment-badge">
              {{ environment }}
            </span>
          </template>
          <span v-else class="version-loading">Loading version...</span>
        </template>
      </div>

      <!-- Copyright/branding + support link (center) -->
      <div class="copyright">
        <div>© {{ currentYear }} Missing Table</div>
        <div class="support-line">
          Need help?
          <SupportEmailLink
            :subject="supportSubject"
            :body="supportBody"
            display-text="Contact support"
            class="support-footer-link"
            data-testid="footer-support-link"
          />
        </div>
      </div>

      <!-- Status indicator (right side) — ops info, admins only -->
      <div class="status-indicator">
        <template v-if="authStore.isAdmin.value && status === 'healthy'">
          <span class="status-dot status-healthy"></span>
          <span class="status-text">Healthy</span>
        </template>
      </div>
    </div>
  </footer>
</template>

<script>
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import SupportEmailLink from '@/components/SupportEmailLink.vue';

export default {
  name: 'VersionFooter',
  components: { SupportEmailLink },
  emits: ['open-whats-new'],
  setup() {
    const authStore = useAuthStore();
    const version = ref(null);
    const environment = ref('unknown');
    const status = ref('healthy');
    const currentYear = computed(() => new Date().getFullYear());
    const errorDismissed = ref(false);

    // Pre-fill support email with the user's account context when logged in.
    // Falls through to a generic "Help request" subject + empty body for
    // anonymous visitors.
    const supportSubject = computed(() => {
      const email = authStore.state.profile?.email;
      return email ? `[Account: ${email}] Help request` : 'Help request';
    });
    const supportBody = computed(() => {
      const profile = authStore.state.profile;
      if (!profile?.email) return '';
      const lines = [
        'Hi support team,',
        '',
        'I need help with my account.',
        '',
        `Account email: ${profile.email}`,
      ];
      if (profile.display_name)
        lines.push(`Display name: ${profile.display_name}`);
      return lines.join('\n');
    });

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
      authStore,
      version,
      environment,
      status,
      currentYear,
      errorDismissed,
      fetchVersion,
      retryFetch,
      supportSubject,
      supportBody,
    };
  },
};
</script>

<style scoped>
.version-footer {
  background-color: rgb(var(--color-surface-alt));
  border-top: 1px solid rgb(var(--color-line));
  padding: 0.75rem 1rem;
  margin-top: 2rem;
  font-size: 0.875rem;
  color: rgb(var(--color-fg-muted));
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
  color: rgb(var(--color-fg));
}

.version-button {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
}

.version-button:hover {
  color: #1e40af;
}

.version-loading {
  color: rgb(var(--color-fg-muted));
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.125rem;
}

.support-line {
  font-size: 0.8125rem;
  color: rgb(var(--color-fg-muted));
}

.support-footer-link {
  font-weight: 500;
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
  color: rgb(var(--color-fg-muted));
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
