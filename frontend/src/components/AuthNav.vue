<template>
  <nav class="auth-nav" data-testid="main-nav">
    <div class="nav-content">
      <div class="nav-brand">
        <img
          src="@/assets/logo.png"
          alt="Missing Table"
          class="nav-logo"
          data-testid="nav-brand"
        />
      </div>

      <div class="nav-links">
        <!-- No navigation links here - they're handled by tabs in App.vue -->

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

export default {
  name: 'AuthNav',
  emits: ['show-login', 'logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
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
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1000;
}

.nav-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
}

.nav-brand {
  display: flex;
  align-items: center;
}

.nav-logo {
  height: 52px;
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
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.user-dropdown:hover {
  background-color: #e9ecef;
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.user-name {
  font-weight: 600;
  color: #333;
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
  color: #666;
  transition: transform 0.2s;
}

.user-dropdown.active .dropdown-arrow {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  min-width: 150px;
  z-index: 1001;
  margin-top: 0.5rem;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  text-decoration: none;
  color: #333;
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s;
}

.dropdown-item:hover {
  background-color: #f8f9fa;
}

.dropdown-divider {
  height: 1px;
  background-color: #dee2e6;
  margin: 0.5rem 0;
}

.logout-item {
  color: #dc3545;
  font-weight: 500;
}

.logout-item:hover {
  background-color: #f8d7da;
}

.login-btn {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 0.5rem 1.5rem;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.login-btn:hover {
  background-color: #0056b3;
}

.loading-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #007bff, #0056b3);
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
