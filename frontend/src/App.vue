<template>
  <div class="min-h-screen bg-gray-100">
    <!-- Navigation -->
    <AuthNav @show-login="showLoginModal = true" @logout="handleLogout" />

    <!-- Login Modal -->
    <div v-if="showLoginModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <button @click="closeModal" class="modal-close">×</button>
        <LoginForm @login-success="handleLoginSuccess" />
      </div>
    </div>

    <!-- Main Content -->
    <div class="container mx-auto px-4 py-8">
      <!-- Hero Section -->
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-blue-600 mb-2">
          The table you've been missing.
        </h1>
        <p class="text-lg text-gray-600">
          Community-built standings, tracking the top youth soccer leagues in
          the US
        </p>
      </div>

      <!-- Loading indicator -->
      <div v-if="authStore.state.loading" class="loading-container">
        <div class="loading-spinner"></div>
        <p>Loading...</p>
      </div>

      <!-- Auth Error Display -->
      <div v-if="authStore.state.error" class="error-banner">
        <p>{{ authStore.state.error }}</p>
        <button @click="authStore.clearError()" class="error-close">×</button>
      </div>

      <!-- Content based on auth status -->
      <div v-if="!authStore.state.loading">
        <!-- Show welcome message if not authenticated -->
        <div v-if="!authStore.state.session" class="max-w-4xl mx-auto">
          <!-- Main Card -->
          <div class="bg-white rounded-lg shadow p-8 text-center mb-6">
            <div class="text-6xl mb-4">🔒</div>
            <h2 class="text-2xl font-bold text-gray-800 mb-4">
              Invite-Only Platform
            </h2>
            <p class="text-gray-600 mb-6">
              Missing Table is an invite-only community platform for tracking
              youth soccer league standings and games.
            </p>
            <div class="flex flex-col sm:flex-row gap-4 justify-center">
              <button
                @click="showLoginModal = true"
                class="bg-blue-600 text-white px-8 py-3 rounded-md font-semibold hover:bg-blue-700 transition-colors text-lg"
              >
                Log In
              </button>
              <button
                @click="showInviteRequestModal = true"
                class="bg-gray-100 text-gray-700 px-8 py-3 rounded-md font-semibold hover:bg-gray-200 transition-colors text-lg border border-gray-300"
              >
                Request Invite
              </button>
            </div>
          </div>

          <!-- Features Section -->
          <div class="grid md:grid-cols-3 gap-4">
            <div class="bg-white rounded-lg shadow p-6 text-center">
              <div class="text-3xl mb-3">📊</div>
              <h3 class="font-semibold text-gray-800 mb-2">Live Standings</h3>
              <p class="text-sm text-gray-600">
                Real-time league tables with automatic point calculations and
                rankings
              </p>
            </div>
            <div class="bg-white rounded-lg shadow p-6 text-center">
              <div class="text-3xl mb-3">📅</div>
              <h3 class="font-semibold text-gray-800 mb-2">Match Tracking</h3>
              <p class="text-sm text-gray-600">
                Track scores, schedules, and results for your team's games
              </p>
            </div>
            <div class="bg-white rounded-lg shadow p-6 text-center">
              <div class="text-3xl mb-3">👥</div>
              <h3 class="font-semibold text-gray-800 mb-2">Team Management</h3>
              <p class="text-sm text-gray-600">
                Manage rosters, match types, and team information all in one
                place
              </p>
            </div>
          </div>
        </div>

        <!-- Invite Request Modal -->
        <div
          v-if="showInviteRequestModal"
          class="modal-overlay"
          @click="showInviteRequestModal = false"
        >
          <div class="modal-content p-6" @click.stop>
            <button @click="showInviteRequestModal = false" class="modal-close">
              ×
            </button>
            <h3 class="text-xl font-bold text-gray-800 mb-4">Request Invite</h3>
            <p class="text-gray-600 mb-4">
              Missing Table is currently invite-only. Please provide your
              information and we'll reach out when spots are available.
            </p>
            <form @submit.prevent="submitInviteRequest" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Email</label
                >
                <input
                  v-model="inviteRequest.email"
                  type="email"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="your@email.com"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Name</label
                >
                <input
                  v-model="inviteRequest.name"
                  type="text"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Team/Club (optional)</label
                >
                <input
                  v-model="inviteRequest.team"
                  type="text"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Your team or club name"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Why do you want to join?</label
                >
                <textarea
                  v-model="inviteRequest.reason"
                  rows="3"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Tell us about your interest in Missing Table"
                ></textarea>
              </div>
              <!-- Honeypot field - hidden from humans, bots will fill it -->
              <div style="position: absolute; left: -9999px" aria-hidden="true">
                <input
                  v-model="inviteRequest.website"
                  type="text"
                  name="website"
                  tabindex="-1"
                  autocomplete="off"
                />
              </div>
              <div class="flex gap-3">
                <button
                  type="submit"
                  :disabled="inviteRequestSubmitting"
                  class="flex-1 bg-blue-600 text-white py-2 rounded-md font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {{
                    inviteRequestSubmitting ? 'Submitting...' : 'Submit Request'
                  }}
                </button>
                <button
                  type="button"
                  @click="showInviteRequestModal = false"
                  class="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
              </div>
            </form>
            <div
              v-if="inviteRequestMessage"
              :class="[
                'mt-4 p-3 rounded-md text-sm',
                inviteRequestSuccess
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800',
              ]"
            >
              {{ inviteRequestMessage }}
            </div>
          </div>
        </div>

        <!-- Tabs for authenticated users -->
        <div v-else class="mb-4">
          <nav class="flex space-x-4" aria-label="Tabs">
            <button
              v-for="tab in availableTabs"
              :key="tab.id"
              @click="currentTab = tab.id"
              :class="[
                currentTab === tab.id
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-500 hover:text-gray-700',
                'px-3 py-2 font-medium text-sm rounded-md',
              ]"
            >
              {{ tab.name }}
            </button>
          </nav>
        </div>

        <!-- Tab Content (only for authenticated users) -->
        <div v-if="authStore.state.session" class="bg-white rounded-lg shadow">
          <!-- Standings -->
          <div v-if="currentTab === 'table'" class="p-4">
            <LeagueTable />
          </div>

          <!-- Matches -->
          <div v-if="currentTab === 'scores'" class="p-4">
            <MatchesView />
          </div>

          <!-- Add Match Form (auth required) -->
          <div v-if="currentTab === 'add-match'" class="p-4">
            <div v-if="!authStore.isAuthenticated" class="auth-required">
              <p>You must be logged in to add matches.</p>
              <button @click="showLoginModal = true" class="login-prompt-btn">
                Login
              </button>
            </div>
            <div v-else-if="!authStore.canManageTeam" class="permission-denied">
              <p>You need team manager or admin permissions to add matches.</p>
            </div>
            <MatchForm v-else />
          </div>

          <!-- Profile (auth required) -->
          <div v-if="currentTab === 'profile'" class="p-4">
            <ProfileRouter
              @logout="handleLogout"
              @switch-tab="handleSwitchTab"
            />
          </div>

          <!-- My Club (players only) -->
          <div v-if="currentTab === 'my-club'" class="p-4">
            <TeamRosterRouter />
          </div>

          <!-- Admin Panel (admin only) -->
          <div v-if="currentTab === 'admin'" class="p-4">
            <AdminPanel />
          </div>
        </div>
      </div>

      <!-- Version Footer -->
      <VersionFooter />
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from './stores/auth';
import { getApiBaseUrl } from './config/api';
import { recordPageView, recordInviteRequest } from './telemetry';
import MatchForm from './components/MatchForm.vue';
import LeagueTable from './components/LeagueTable.vue';
import MatchesView from './components/MatchesView.vue';
import AuthNav from './components/AuthNav.vue';
import LoginForm from './components/LoginForm.vue';
import ProfileRouter from './components/ProfileRouter.vue';
import TeamRosterRouter from './components/profiles/TeamRosterRouter.vue';
import AdminPanel from './components/AdminPanel.vue';
import VersionFooter from './components/VersionFooter.vue';

export default {
  name: 'App',
  components: {
    MatchForm,
    LeagueTable,
    MatchesView,
    AuthNav,
    LoginForm,
    ProfileRouter,
    TeamRosterRouter,
    AdminPanel,
    VersionFooter,
  },
  setup() {
    const authStore = useAuthStore();
    const currentTab = ref('table');
    const showLoginModal = ref(false);
    const showInviteRequestModal = ref(false);
    const inviteRequest = ref({
      email: '',
      name: '',
      team: '',
      reason: '',
      website: '', // Honeypot field - bots will fill this
    });
    const inviteRequestSubmitting = ref(false);
    const inviteRequestMessage = ref('');
    const inviteRequestSuccess = ref(false);

    // Define all possible tabs
    const allTabs = [
      { id: 'table', name: 'Table', requiresAuth: true },
      { id: 'scores', name: 'Matches', requiresAuth: true },
      {
        id: 'add-match',
        name: 'Add Match',
        requiresAuth: true,
        requiresRole: ['admin', 'club_manager', 'team-manager'],
      },
      {
        id: 'my-club',
        name: 'My Club',
        requiresAuth: true,
        requiresRole: ['team-player'],
      },
      {
        id: 'admin',
        name: 'Admin',
        requiresAuth: true,
        requiresRole: ['admin', 'club_manager'],
      },
      { id: 'profile', name: 'Profile', requiresAuth: true },
    ];

    // Computed property for available tabs based on user's auth status and role
    const availableTabs = computed(() => {
      const userRole = authStore.userRole.value;

      return allTabs
        .filter(tab => {
          // Always show public tabs
          if (!tab.requiresAuth) return true;

          // Don't show auth-required tabs if user is not authenticated
          if (!authStore.isAuthenticated.value) return false;

          // Check role requirements
          if (tab.requiresRole) {
            return tab.requiresRole.includes(userRole);
          }

          return true;
        })
        .map(tab => {
          // Rename "Admin" tab to "Manage Club" for club managers
          if (tab.id === 'admin' && userRole === 'club_manager') {
            return { ...tab, name: 'Manage Club' };
          }
          return tab;
        });
    });

    const closeModal = () => {
      showLoginModal.value = false;
    };

    const handleLoginSuccess = () => {
      showLoginModal.value = false;
      // Optionally redirect to profile or keep current tab
    };

    const handleLogout = () => {
      // Reset to public tab if current tab requires auth
      const currentTabData = allTabs.find(t => t.id === currentTab.value);
      if (currentTabData && currentTabData.requiresAuth) {
        currentTab.value = 'table';
      }
    };

    const handleSwitchTab = tabId => {
      // Switch to the requested tab
      currentTab.value = tabId;
    };

    const submitInviteRequest = async () => {
      inviteRequestSubmitting.value = true;
      inviteRequestMessage.value = '';

      try {
        const response = await fetch(`${getApiBaseUrl()}/api/invite-requests`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(inviteRequest.value),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          inviteRequestSuccess.value = true;
          inviteRequestMessage.value = data.message;
          recordInviteRequest(true);

          // Reset form
          inviteRequest.value = {
            email: '',
            name: '',
            team: '',
            reason: '',
            website: '',
          };
        } else {
          inviteRequestSuccess.value = false;
          inviteRequestMessage.value =
            data.detail || 'Failed to submit request. Please try again.';
          recordInviteRequest(false);
        }
      } catch (error) {
        inviteRequestSuccess.value = false;
        inviteRequestMessage.value =
          'Failed to submit request. Please try again.';
        recordInviteRequest(false);
      } finally {
        inviteRequestSubmitting.value = false;
      }
    };

    // Watch for tab changes and record page views
    watch(currentTab, newTab => {
      recordPageView(newTab, {
        authenticated: authStore.isAuthenticated.value ? 'true' : 'false',
        user_role: authStore.userRole.value || 'anonymous',
      });
    });

    // Initialize auth on app start
    onMounted(async () => {
      // For testing - uncomment the next line to force logout on each page load
      // authStore.forceLogout()

      await authStore.initialize();

      // Record initial page view after auth initialization
      recordPageView(currentTab.value, {
        authenticated: authStore.isAuthenticated.value ? 'true' : 'false',
        user_role: authStore.userRole.value || 'anonymous',
      });

      // Check for invite code in URL - automatically open login modal for signup
      const urlParams = new URLSearchParams(window.location.search);
      const inviteCode = urlParams.get('code');
      if (inviteCode && !authStore.isAuthenticated.value) {
        showLoginModal.value = true;
      }
    });

    return {
      authStore,
      currentTab,
      availableTabs,
      showLoginModal,
      showInviteRequestModal,
      inviteRequest,
      inviteRequestSubmitting,
      inviteRequestMessage,
      inviteRequestSuccess,
      closeModal,
      handleLoginSuccess,
      handleLogout,
      handleSwitchTab,
      submitInviteRequest,
    };
  },
};
</script>

<style>
/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  position: relative;
  background: white;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-close {
  position: absolute;
  top: 10px;
  right: 15px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  z-index: 1001;
}

.modal-close:hover {
  color: #333;
}

/* Loading styles */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* Error banner */
.error-banner {
  background-color: #f8d7da;
  color: #721c24;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.error-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #721c24;
}

/* Auth prompts */
.auth-required,
.permission-denied {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.login-prompt-btn {
  background-color: #007bff;
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 1rem;
}

.login-prompt-btn:hover {
  background-color: #0056b3;
}
</style>
