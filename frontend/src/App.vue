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
      <h1 class="text-3xl font-bold text-blue-600 mb-8">
        Missing Table - Tracking U13 & U14 MLS Next Season
      </h1>
      
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
        <!-- Public Content (always visible) -->
        <div class="mb-4">
          <nav class="flex space-x-4" aria-label="Tabs">
            <button
              v-for="tab in availableTabs"
              :key="tab.id"
              @click="currentTab = tab.id"
              :class="[
                currentTab === tab.id
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-500 hover:text-gray-700',
                'px-3 py-2 font-medium text-sm rounded-md'
              ]"
            >
              {{ tab.name }}
            </button>
          </nav>
        </div>

        <!-- Tab Content -->
        <div class="bg-white rounded-lg shadow">
          <!-- Standings -->
          <div v-if="currentTab === 'table'" class="p-4">
            <h2 class="text-xl font-semibold mb-4">League Standings</h2>
            <LeagueTable />
          </div>

          <!-- Games -->
          <div v-if="currentTab === 'scores'" class="p-4">
            <h2 class="text-xl font-semibold mb-4">Games</h2>
            <ScoresSchedule />
          </div>

          <!-- Add Game Form (auth required) -->
          <div v-if="currentTab === 'add-game'" class="p-4">
            <h2 class="text-xl font-semibold mb-4">Schedule/Score Game</h2>
            <div v-if="!authStore.isAuthenticated" class="auth-required">
              <p>You must be logged in to add games.</p>
              <button @click="showLoginModal = true" class="login-prompt-btn">
                Login
              </button>
            </div>
            <div v-else-if="!authStore.canManageTeam" class="permission-denied">
              <p>You need team manager or admin permissions to add games.</p>
            </div>
            <GameForm v-else />
          </div>

          <!-- Profile (auth required) -->
          <div v-if="currentTab === 'profile'" class="p-4">
            <ProfileRouter @logout="handleLogout" />
          </div>

          <!-- Admin Panel (admin only) -->
          <div v-if="currentTab === 'admin'" class="p-4">
            <h2 class="text-xl font-semibold mb-4">Admin Panel</h2>
            <AdminPanel />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import GameForm from './components/GameForm.vue'
import LeagueTable from './components/LeagueTable.vue'
import ScoresSchedule from './components/ScoresSchedule.vue'
import AuthNav from './components/AuthNav.vue'
import LoginForm from './components/LoginForm.vue'
import ProfileRouter from './components/ProfileRouter.vue'
import AdminPanel from './components/AdminPanel.vue'

export default {
  name: 'App',
  components: {
    GameForm,
    LeagueTable,
    ScoresSchedule,
    AuthNav,
    LoginForm,
    ProfileRouter,
    AdminPanel
  },
  setup() {
    const authStore = useAuthStore()
    const currentTab = ref('table')
    const showLoginModal = ref(false)

    // Define all possible tabs
    const allTabs = [
      { id: 'table', name: 'Standings', requiresAuth: false },
      { id: 'scores', name: 'Games', requiresAuth: false },
      { id: 'add-game', name: 'Add Game', requiresAuth: true, requiresRole: ['admin', 'team-manager'] },
      { id: 'profile', name: 'Profile', requiresAuth: true },
      { id: 'admin', name: 'Admin', requiresAuth: true, requiresRole: ['admin'] }
    ]

    // Computed property for available tabs based on user's auth status and role
    const availableTabs = computed(() => {
      return allTabs.filter(tab => {
        // Always show public tabs
        if (!tab.requiresAuth) return true
        
        // Don't show auth-required tabs if user is not authenticated
        if (!authStore.isAuthenticated.value) return false
        
        // Check role requirements
        if (tab.requiresRole) {
          const userRole = authStore.userRole.value
          return tab.requiresRole.includes(userRole)
        }
        
        return true
      })
    })

    const closeModal = () => {
      showLoginModal.value = false
    }


    const handleLoginSuccess = () => {
      showLoginModal.value = false
      // Optionally redirect to profile or keep current tab
    }

    const handleLogout = () => {
      // Reset to public tab if current tab requires auth
      const currentTabData = allTabs.find(t => t.id === currentTab.value)
      if (currentTabData && currentTabData.requiresAuth) {
        currentTab.value = 'table'
      }
    }

    // Initialize auth on app start
    onMounted(async () => {
      // For testing - uncomment the next line to force logout on each page load
      // authStore.forceLogout()
      
      await authStore.initialize()
    })

    return {
      authStore,
      currentTab,
      availableTabs,
      showLoginModal,
      closeModal,
      handleLoginSuccess,
      handleLogout
    }
  }
}
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
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
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
.auth-required, .permission-denied {
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