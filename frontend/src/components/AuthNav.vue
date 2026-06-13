<template>
  <nav class="auth-nav" data-testid="main-nav">
    <div class="nav-content container mx-auto px-4">
      <div class="nav-brand" :class="{ 'nav-brand--chip': isDark }">
        <img
          src="@/assets/logo.png"
          alt="Missing Table"
          class="nav-logo"
          data-testid="nav-brand"
        />
      </div>

      <div class="nav-links">
        <!-- No navigation links here - they're handled by tabs in App.vue -->

        <!-- Theme toggle (available to everyone, incl. logged-out) -->
        <button
          class="theme-toggle"
          type="button"
          data-testid="theme-toggle"
          :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          :aria-pressed="isDark"
          @click="toggleTheme"
        >
          <svg
            v-if="isDark"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="theme-toggle-icon"
          >
            <circle cx="12" cy="12" r="4" />
            <path
              d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
            />
          </svg>
          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="theme-toggle-icon"
          >
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </button>

        <!-- Authenticated user menu -->
        <div
          v-if="authStore.isAuthenticated.value"
          class="user-menu"
          data-testid="user-menu"
        >
          <!-- User dropdown -->
          <div
            class="user-dropdown"
            @click="toggleDropdown"
            data-testid="user-dropdown"
          >
            <div class="user-info">
              <span class="user-name" data-testid="user-name">
                {{ authStore.state.profile?.display_name || 'User' }}
              </span>
              <span
                class="user-role"
                :class="roleClass"
                data-testid="user-role"
              >
                {{ formatRole(authStore.userRole) }}
              </span>
            </div>
            <div class="dropdown-arrow">▼</div>
          </div>

          <div
            v-if="showDropdown"
            class="dropdown-menu"
            data-testid="dropdown-menu"
          >
            <button
              @click="handleLogout"
              class="dropdown-item logout-item"
              data-testid="logout-button"
            >
              Logout
            </button>
          </div>
        </div>

        <!-- Login button for non-authenticated users -->
        <button
          v-else
          @click="showLogin"
          class="login-btn"
          data-testid="nav-login-button"
        >
          Login
        </button>
      </div>
    </div>

    <!-- Loading indicator -->
    <div
      v-if="authStore.state.loading"
      class="loading-bar"
      data-testid="loading-bar"
    ></div>
  </nav>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useTheme } from '@/composables/useTheme';

export default {
  name: 'AuthNav',
  emits: ['show-login', 'logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const { isDark, toggle: toggleTheme } = useTheme();
    const showDropdown = ref(false);

    const roleClass = computed(() => {
      const role = authStore.userRole.value;
      return (
        {
          admin: 'role-admin',
          club_manager: 'role-manager',
          'team-manager': 'role-manager',
          team_manager: 'role-manager',
          'team-player': 'role-player',
          club_fan: 'role-fan',
          'team-fan': 'role-fan',
        }[role] || 'role-fan'
      );
    });

    const formatRole = roleRef => {
      // Handle both ref and plain value
      const role = roleRef?.value ?? roleRef;

      // For club fans, show club name
      if (role === 'club_fan') {
        const clubName = authStore.state.profile?.club?.name;
        if (clubName) {
          return `${clubName} Fan`;
        }
        return 'Club Fan';
      }

      // For club managers, show club name
      if (role === 'club_manager') {
        const clubName = authStore.state.profile?.club?.name;
        if (clubName) {
          return `${clubName} Manager`;
        }
        return 'Club Manager';
      }

      // For players and fans, show team name instead of role
      if (role === 'team-player' || role === 'team-fan') {
        const teamName = authStore.state.profile?.team?.name;
        if (teamName) {
          return teamName;
        }
      }

      // For admin and manager, show role name
      const roleNames = {
        admin: 'Admin',
        'team-manager': 'Manager',
        team_manager: 'Manager',
        'team-player': 'Player',
        'team-fan': 'Fan',
      };
      return roleNames[role] || role;
    };

    const toggleDropdown = () => {
      showDropdown.value = !showDropdown.value;
    };

    const hideDropdown = () => {
      showDropdown.value = false;
    };

    const showLogin = () => {
      emit('show-login');
    };

    const handleLogout = async () => {
      hideDropdown();
      const result = await authStore.logout();
      if (result.success) {
        emit('logout');
      }
    };

    // Close dropdown when clicking outside
    const handleClickOutside = event => {
      if (!event.target.closest('.user-dropdown')) {
        hideDropdown();
      }
    };

    onMounted(() => {
      document.addEventListener('click', handleClickOutside);
    });

    onUnmounted(() => {
      document.removeEventListener('click', handleClickOutside);
    });

    return {
      authStore,
      isDark,
      toggleTheme,
      showDropdown,
      roleClass,
      formatRole,
      toggleDropdown,
      hideDropdown,
      showLogin,
      handleLogout,
    };
  },
};
</script>

<style scoped>
.auth-nav {
  background-color: rgb(var(--color-card));
  border-bottom: 1px solid rgb(var(--color-line));
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1000;
}

.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 8px;
  background: none;
  color: rgb(var(--color-fg-muted));
  cursor: pointer;
  transition:
    background-color 0.2s,
    color 0.2s;
}

.theme-toggle:hover {
  background-color: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
}

.theme-toggle-icon {
  width: 20px;
  height: 20px;
}

.nav-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
}

.nav-brand {
  display: flex;
  align-items: center;
}

/* Interim dark-mode logo treatment (SB-148): the logo art has a white
   background baked in, so on the dark nav we frame it as an intentional
   white chip instead of a stray box. Removed once a proper asset lands. */
.nav-brand--chip {
  background-color: #ffffff;
  padding: 4px 10px;
  border-radius: 10px;
}

.nav-logo {
  height: 72px;
  width: auto;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  position: relative;
}

.nav-link {
  text-decoration: none;
  color: #555;
  font-weight: 500;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: all 0.2s;
}

.nav-link:hover {
  color: #007bff;
  background-color: #f8f9fa;
}

.nav-link.router-link-active {
  color: #007bff;
  background-color: #e3f2fd;
}

.admin-link {
  color: #dc3545 !important;
}

.admin-link:hover {
  background-color: #f8d7da !important;
}

.manager-link {
  color: #007bff !important;
}

.manager-link:hover {
  background-color: #d1ecf1 !important;
}

.user-menu {
  position: relative;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background-color: rgb(var(--color-surface-alt));
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.user-dropdown:hover {
  background-color: rgb(var(--color-line));
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.user-name {
  font-weight: 600;
  color: rgb(var(--color-fg));
  font-size: 0.9rem;
}

.user-role {
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.user-role.role-admin {
  color: #dc3545;
}

.user-role.role-manager {
  color: #007bff;
}

.user-role.role-player {
  color: #28a745;
}

.user-role.role-fan {
  color: #6c757d;
}

.dropdown-arrow {
  font-size: 0.7rem;
  color: #94a3b8;
  transition: transform 0.2s;
}

.user-role.role-admin {
  color: #dc2626;
}

.user-role.role-manager {
  color: #2563eb;
}

.user-role.role-player {
  color: #16a34a;
}

.user-role.role-fan {
  color: #64748b;
}

.user-dropdown.active .dropdown-arrow {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  min-width: 150px;
  z-index: 1001;
  margin-top: 0.5rem;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  text-decoration: none;
  color: #374151;
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s;
}

.dropdown-item:hover {
  background-color: #f8fafc;
}

.dropdown-divider {
  height: 1px;
  background-color: #e2e8f0;
  margin: 0.5rem 0;
}

.logout-item {
  color: #dc2626;
  font-weight: 500;
}

.logout-item:hover {
  background-color: #fef2f2;
}

.login-btn {
  background-color: #1e40af;
  color: white;
  border: none;
  padding: 0.5rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.login-btn:hover {
  background-color: #1a3793;
}

.loading-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #1e40af, #aac3ea);
  animation: loading 1.5s ease-in-out infinite;
}

@keyframes loading {
  0% {
    transform: translateX(-100%);
  }
  50% {
    transform: translateX(0%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .nav-content {
    padding: 1rem;
  }

  .nav-links {
    gap: 1rem;
  }

  .nav-link {
    padding: 0.25rem 0.5rem;
    font-size: 0.9rem;
  }

  .user-dropdown {
    padding: 0.25rem 0.5rem;
  }

  .user-name {
    font-size: 0.8rem;
  }

  .user-role {
    font-size: 0.7rem;
  }
}
</style>
