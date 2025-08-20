<template>
  <div class="profile-router">
    <div v-if="authStore.state.loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>Loading your profile...</p>
    </div>

    <div v-else-if="!authStore.isAuthenticated" class="not-authenticated">
      <h3>Authentication Required</h3>
      <p>Please log in to view your profile.</p>
    </div>

    <div v-else-if="!authStore.state.profile" class="no-profile">
      <h3>Profile Not Found</h3>
      <p>Unable to load your profile. Please try refreshing the page.</p>
      <button @click="refreshProfile" class="refresh-btn">
        Refresh Profile
      </button>
    </div>

    <div v-else class="profile-content">
      <!-- Admin Profile -->
      <AdminProfile v-if="userRole === 'admin'" @logout="handleLogout" />

      <!-- Team Manager Profile -->
      <TeamManagerProfile
        v-else-if="userRole === 'team-manager'"
        @logout="handleLogout"
      />

      <!-- Player Profile -->
      <PlayerProfile
        v-else-if="userRole === 'team-player'"
        @logout="handleLogout"
      />

      <!-- Fan Profile (default) -->
      <FanProfile v-else @logout="handleLogout" />
    </div>

    <!-- Role Debug Info (only in development) -->
    <div v-if="showDebug" class="debug-info">
      <h4>Debug Information</h4>
      <div class="debug-details">
        <p><strong>User Role:</strong> {{ userRole }}</p>
        <p>
          <strong>Is Authenticated:</strong> {{ authStore.isAuthenticated }}
        </p>
        <p><strong>Profile Loaded:</strong> {{ !!authStore.state.profile }}</p>
        <p><strong>User ID:</strong> {{ authStore.state.user?.id }}</p>
        <p><strong>Email:</strong> {{ authStore.state.user?.email }}</p>
      </div>
      <button @click="showDebug = false" class="close-debug">
        Close Debug
      </button>
    </div>

    <!-- Debug Toggle (only in development) -->
    <button
      v-if="isDevelopment && !showDebug"
      @click="showDebug = true"
      class="debug-toggle"
    >
      🐛 Debug
    </button>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import AdminProfile from './profiles/AdminProfile.vue';
import TeamManagerProfile from './profiles/TeamManagerProfile.vue';
import PlayerProfile from './profiles/PlayerProfile.vue';
import FanProfile from './profiles/FanProfile.vue';

export default {
  name: 'ProfileRouter',
  components: {
    AdminProfile,
    TeamManagerProfile,
    PlayerProfile,
    FanProfile,
  },
  emits: ['logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const showDebug = ref(false);

    const userRole = computed(() => {
      return authStore.state.profile?.role || 'team-fan';
    });

    const isDevelopment = computed(() => {
      return process.env.NODE_ENV === 'development';
    });

    const refreshProfile = async () => {
      try {
        await authStore.fetchProfile();
      } catch (error) {
        console.error('Error refreshing profile:', error);
        authStore.setError('Failed to refresh profile');
      }
    };

    const handleLogout = () => {
      emit('logout');
    };

    onMounted(() => {
      // Ensure profile is loaded when component mounts
      if (authStore.isAuthenticated && !authStore.state.profile) {
        refreshProfile();
      }
    });

    return {
      authStore,
      userRole,
      isDevelopment,
      showDebug,
      refreshProfile,
      handleLogout,
    };
  },
};
</script>

<style scoped>
.profile-router {
  min-height: 100vh;
  position: relative;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e5e7eb;
  border-top: 4px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.loading-state p {
  color: #6b7280;
  font-size: 16px;
  margin: 0;
}

.not-authenticated,
.no-profile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  background-color: #f9fafb;
  border-radius: 8px;
  margin: 20px;
  border: 1px solid #e5e7eb;
}

.not-authenticated h3,
.no-profile h3 {
  color: #1f2937;
  margin-bottom: 15px;
  font-size: 24px;
}

.not-authenticated p,
.no-profile p {
  color: #6b7280;
  margin-bottom: 20px;
  font-size: 16px;
}

.refresh-btn {
  background-color: #3b82f6;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s ease;
}

.refresh-btn:hover {
  background-color: #2563eb;
}

.profile-content {
  min-height: 100vh;
}

/* Debug Information Styles */
.debug-info {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: white;
  border: 2px solid #f59e0b;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
  max-width: 300px;
  z-index: 1000;
}

.debug-info h4 {
  color: #f59e0b;
  margin: 0 0 15px 0;
  font-size: 16px;
  border-bottom: 1px solid #fde68a;
  padding-bottom: 8px;
}

.debug-details p {
  margin: 8px 0;
  font-size: 12px;
  color: #374151;
  word-break: break-all;
}

.debug-details strong {
  color: #1f2937;
}

.close-debug {
  background-color: #f59e0b;
  color: white;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  margin-top: 10px;
  width: 100%;
}

.close-debug:hover {
  background-color: #d97706;
}

.debug-toggle {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background-color: #f59e0b;
  color: white;
  padding: 10px 15px;
  border: none;
  border-radius: 50px;
  cursor: pointer;
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 999;
  transition: all 0.2s ease;
}

.debug-toggle:hover {
  background-color: #d97706;
  transform: scale(1.05);
}

/* Responsive Design */
@media (max-width: 768px) {
  .debug-info {
    bottom: 10px;
    right: 10px;
    left: 10px;
    max-width: none;
  }

  .debug-toggle {
    bottom: 10px;
    right: 10px;
    padding: 8px 12px;
    font-size: 12px;
  }

  .loading-state,
  .not-authenticated,
  .no-profile {
    padding: 40px 15px;
  }

  .not-authenticated h3,
  .no-profile h3 {
    font-size: 20px;
  }

  .not-authenticated p,
  .no-profile p {
    font-size: 14px;
  }
}

/* Dark mode support (if needed in the future) */
@media (prefers-color-scheme: dark) {
  .debug-info {
    background: #1f2937;
    border-color: #f59e0b;
    color: #f3f4f6;
  }

  .debug-details strong {
    color: #e5e7eb;
  }

  .not-authenticated,
  .no-profile {
    background-color: #1f2937;
    border-color: #374151;
  }

  .not-authenticated h3,
  .no-profile h3 {
    color: #f3f4f6;
  }

  .not-authenticated p,
  .no-profile p {
    color: #9ca3af;
  }
}
</style>
