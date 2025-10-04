<template>
  <BaseProfile title="Administrator Dashboard" @logout="$emit('logout')">
    <template #profile-fields>
      <div class="info-group">
        <label>Admin Level:</label>
        <span class="admin-level">Super Administrator</span>
      </div>
      <div class="info-group">
        <label>Permissions:</label>
        <span class="permissions">Full System Access</span>
      </div>
    </template>

    <template #profile-sections>
      <!-- Admin Management Section -->
      <div class="admin-section">
        <h3>Administrative Functions</h3>
        <div class="admin-grid">
          <div
            class="admin-card"
            @click="showUserManagement = !showUserManagement"
          >
            <div class="card-icon">👥</div>
            <h4>User Management</h4>
            <p>Manage user roles and permissions</p>
          </div>

          <div class="admin-card" @click="navigateToAdmin">
            <div class="card-icon">⚙️</div>
            <h4>System Administration</h4>
            <p>Manage teams, games, and leagues</p>
          </div>

          <div class="admin-card">
            <div class="card-icon">📊</div>
            <h4>Analytics</h4>
            <p>View system statistics and reports</p>
          </div>

          <div class="admin-card">
            <div class="card-icon">🛠️</div>
            <h4>System Settings</h4>
            <p>Configure application settings</p>
          </div>
        </div>
      </div>

      <!-- User Management Panel -->
      <div v-if="showUserManagement" class="user-management-section">
        <div class="section-header">
          <h3>User Management</h3>
          <button @click="showUserManagement = false" class="close-btn">
            ×
          </button>
        </div>

        <div v-if="loadingUsers" class="loading">Loading users...</div>
        <div v-else class="users-grid">
          <div v-for="user in users" :key="user.id" class="user-card">
            <div class="user-avatar">
              {{ getInitials(user.display_name || user.email) }}
            </div>
            <div class="user-details">
              <h4>{{ user.display_name || 'No name' }}</h4>
              <p class="user-email">{{ user.email || 'No email' }}</p>
              <span class="role-badge" :class="getRoleClass(user.role)">
                {{ formatRole(user.role) }}
              </span>
              <div v-if="user.team" class="user-team">
                Team: {{ user.team.name }}
              </div>
            </div>
            <div class="user-actions">
              <select
                :value="user.role"
                @change="updateUserRole(user.id, $event.target.value)"
                class="role-select"
              >
                <option value="team-fan">Team Fan</option>
                <option value="team-player">Team Player</option>
                <option value="team-manager">Team Manager</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Stats -->
      <div class="quick-stats">
        <h3>Quick Statistics</h3>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-number">{{ users.length }}</div>
            <div class="stat-label">Total Users</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ adminCount }}</div>
            <div class="stat-label">Administrators</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ managerCount }}</div>
            <div class="stat-label">Team Managers</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ playerCount }}</div>
            <div class="stat-label">Players</div>
          </div>
        </div>
      </div>
    </template>
  </BaseProfile>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import BaseProfile from './BaseProfile.vue';

export default {
  name: 'AdminProfile',
  components: {
    BaseProfile,
  },
  emits: ['logout'],
  setup() {
    const authStore = useAuthStore();
    const showUserManagement = ref(false);
    const loadingUsers = ref(false);
    const users = ref([]);

    const adminCount = computed(
      () => users.value.filter(u => u.role === 'admin').length
    );
    const managerCount = computed(
      () => users.value.filter(u => u.role === 'team-manager').length
    );
    const playerCount = computed(
      () => users.value.filter(u => u.role === 'team-player').length
    );

    const fetchUsers = async () => {
      if (!authStore.isAdmin) return;

      try {
        loadingUsers.value = true;
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/auth/users`
        );
        users.value = response;
      } catch (error) {
        console.error('Error fetching users:', error);
        if (!error.message.includes('403')) {
          authStore.setError('Failed to load users');
        }
      } finally {
        loadingUsers.value = false;
      }
    };

    const updateUserRole = async (userId, newRole) => {
      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/auth/users/role`,
          {
            method: 'PUT',
            body: JSON.stringify({
              user_id: userId,
              role: newRole,
            }),
          }
        );
        await fetchUsers();
      } catch (error) {
        console.error('Error updating user role:', error);
        authStore.setError('Failed to update user role');
      }
    };

    const formatRole = role => {
      const roleMap = {
        admin: 'Administrator',
        'team-manager': 'Team Manager',
        'team-player': 'Team Player',
        'team-fan': 'Team Fan',
      };
      return roleMap[role] || role;
    };

    const getRoleClass = role => {
      return `role-${role?.replace('team-', '') || 'fan'}`;
    };

    const getInitials = name => {
      if (!name) return '?';
      return name
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    };

    const navigateToAdmin = () => {
      // This would typically use vue-router
      // For now, just emit an event or use direct navigation
      console.log('Navigate to admin panel');
    };

    onMounted(async () => {
      if (authStore.isAdmin) {
        await fetchUsers();
      }
    });

    return {
      showUserManagement,
      loadingUsers,
      users,
      adminCount,
      managerCount,
      playerCount,
      fetchUsers,
      updateUserRole,
      formatRole,
      getRoleClass,
      getInitials,
      navigateToAdmin,
    };
  },
};
</script>

<style scoped>
.admin-section {
  background-color: #f8fafc;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.admin-section h3 {
  color: #1e40af;
  margin-bottom: 20px;
  font-size: 18px;
}

.admin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.admin-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
}

.admin-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-color: #3b82f6;
}

.card-icon {
  font-size: 24px;
  margin-bottom: 10px;
}

.admin-card h4 {
  color: #1f2937;
  margin: 10px 0 5px 0;
  font-size: 16px;
}

.admin-card p {
  color: #6b7280;
  font-size: 14px;
  margin: 0;
}

.user-management-section {
  background-color: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #6b7280;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #dc2626;
}

.users-grid {
  display: grid;
  gap: 15px;
  padding: 20px;
}

.user-card {
  display: flex;
  align-items: center;
  padding: 15px;
  background-color: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.user-avatar {
  width: 50px;
  height: 50px;
  background-color: #3b82f6;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 15px;
}

.user-details {
  flex: 1;
}

.user-details h4 {
  margin: 0 0 5px 0;
  color: #1f2937;
  font-size: 16px;
}

.user-email {
  color: #6b7280;
  font-size: 14px;
  margin: 0 0 8px 0;
}

.user-team {
  color: #059669;
  font-size: 12px;
  margin-top: 5px;
}

.role-select {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  min-width: 140px;
}

.quick-stats {
  background-color: #f0f9ff;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #bae6fd;
}

.quick-stats h3 {
  color: #0c4a6e;
  margin-bottom: 15px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 15px;
}

.stat-item {
  text-align: center;
  background: white;
  padding: 15px;
  border-radius: 6px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #1e40af;
  margin-bottom: 5px;
}

.stat-label {
  color: #6b7280;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.admin-level {
  color: #dc2626;
  font-weight: 600;
}

.permissions {
  color: #059669;
  font-weight: 600;
}

.role-admin {
  background-color: #fee2e2;
  color: #dc2626;
}
.role-manager {
  background-color: #dbeafe;
  color: #2563eb;
}
.role-player {
  background-color: #d1fae5;
  color: #059669;
}
.role-fan {
  background-color: #e5e7eb;
  color: #6b7280;
}
</style>
