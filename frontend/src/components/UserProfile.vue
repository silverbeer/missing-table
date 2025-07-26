<template>
  <div class="user-profile">
    <div class="profile-header">
      <h2>User Profile</h2>
      <button @click="handleLogout" class="logout-btn">
        Logout
      </button>
    </div>

    <div v-if="authStore.state.loading" class="loading">
      Loading profile...
    </div>

    <div v-else-if="authStore.state.profile" class="profile-content">
      <div class="profile-info">
        <div class="info-group">
          <label>Email:</label>
          <span>{{ authStore.state.user?.email }}</span>
        </div>

        <div class="info-group">
          <label>Display Name:</label>
          <input
            v-model="editForm.display_name"
            type="text"
            :disabled="!isEditing"
            class="profile-input"
          />
        </div>

        <div class="info-group">
          <label>Role:</label>
          <span class="role-badge" :class="roleClass">
            {{ formatRole(authStore.state.profile.role) }}
          </span>
        </div>

        <div v-if="authStore.state.profile.team" class="info-group">
          <label>Team:</label>
          <span>{{ authStore.state.profile.team.name }} ({{ authStore.state.profile.team.city }})</span>
        </div>

        <div class="info-group">
          <label>Member Since:</label>
          <span>{{ formatDate(authStore.state.profile.created_at) }}</span>
        </div>
      </div>

      <div class="profile-actions">
        <button 
          v-if="!isEditing" 
          @click="startEditing" 
          class="edit-btn"
        >
          Edit Profile
        </button>
        
        <div v-else class="edit-actions">
          <button @click="saveChanges" :disabled="saving" class="save-btn">
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
          <button @click="cancelEditing" class="cancel-btn">
            Cancel
          </button>
        </div>
      </div>

      <!-- Team Selection for managers/players -->
      <div v-if="isEditing && showTeamSelection" class="team-selection">
        <label for="teamSelect">Team:</label>
        <select id="teamSelect" v-model="editForm.team_id">
          <option value="">No team</option>
          <option v-for="team in teams" :key="team.id" :value="team.id">
            {{ team.name }} ({{ team.city }})
          </option>
        </select>
      </div>

      <div v-if="authStore.state.error" class="error-message">
        {{ authStore.state.error }}
      </div>
    </div>

    <!-- Admin Panel -->
    <div v-if="authStore.isAdmin" class="admin-panel">
      <h3>Admin Panel</h3>
      <div class="admin-actions">
        <button @click="showUserManagement = !showUserManagement" class="admin-btn">
          {{ showUserManagement ? 'Hide' : 'Show' }} User Management
        </button>
      </div>

      <div v-if="showUserManagement" class="user-management">
        <h4>Manage Users</h4>
        <div v-if="loadingUsers" class="loading">Loading users...</div>
        <div v-else class="users-list">
          <div v-for="user in users" :key="user.id" class="user-item">
            <div class="user-info">
              <strong>{{ user.display_name || 'No name' }}</strong>
              <span class="user-email">{{ user.email || 'No email' }}</span>
              <span class="role-badge" :class="getRoleClass(user.role)">
                {{ formatRole(user.role) }}
              </span>
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
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

export default {
  name: 'UserProfile',
  emits: ['logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore()
    const isEditing = ref(false)
    const saving = ref(false)
    const showUserManagement = ref(false)
    const loadingUsers = ref(false)
    const users = ref([])
    const teams = ref([])

    const editForm = reactive({
      display_name: '',
      team_id: null
    })

    const showTeamSelection = computed(() => {
      const role = authStore.state.profile?.role
      return role === 'team-manager' || role === 'team-player'
    })

    const roleClass = computed(() => {
      return getRoleClass(authStore.state.profile?.role)
    })

    const getRoleClass = (role) => {
      const classes = {
        'admin': 'role-admin',
        'team-manager': 'role-manager',
        'team-player': 'role-player',
        'team-fan': 'role-fan'
      }
      return classes[role] || 'role-fan'
    }

    const formatRole = (role) => {
      const roleNames = {
        'admin': 'Administrator',
        'team-manager': 'Team Manager',
        'team-player': 'Team Player',
        'team-fan': 'Team Fan'
      }
      return roleNames[role] || role
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleDateString()
    }

    const startEditing = () => {
      isEditing.value = true
      editForm.display_name = authStore.state.profile.display_name || ''
      editForm.team_id = authStore.state.profile.team_id || null
    }

    const cancelEditing = () => {
      isEditing.value = false
      authStore.clearError()
    }

    const saveChanges = async () => {
      saving.value = true
      authStore.clearError()

      try {
        const updates = {}
        if (editForm.display_name !== authStore.state.profile.display_name) {
          updates.display_name = editForm.display_name
        }
        if (editForm.team_id !== authStore.state.profile.team_id) {
          updates.team_id = editForm.team_id
        }

        if (Object.keys(updates).length > 0) {
          const result = await authStore.updateProfile(updates)
          if (result.success) {
            isEditing.value = false
          }
        } else {
          isEditing.value = false
        }
      } catch (error) {
        authStore.setError('Failed to update profile')
      } finally {
        saving.value = false
      }
    }

    const handleLogout = async () => {
      const result = await authStore.logout()
      if (result.success) {
        emit('logout')
      }
    }

    const fetchUsers = async () => {
      if (!authStore.isAdmin) {
        console.log('Not admin, skipping user fetch')
        return
      }

      try {
        loadingUsers.value = true
        const response = await authStore.apiRequest('http://localhost:8000/api/auth/users')
        users.value = response
        console.log('Successfully fetched users for admin')
      } catch (error) {
        console.error('Error fetching users:', error)
        // Don't show error to user if it's just an authorization issue
        if (error.message.includes('403') || error.message.includes('Forbidden')) {
          console.log('User does not have admin access')
        } else {
          authStore.setError('Failed to load users')
        }
      } finally {
        loadingUsers.value = false
      }
    }

    const fetchTeams = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/teams')
        const data = await response.json()
        teams.value = data
      } catch (error) {
        console.error('Error fetching teams:', error)
      }
    }

    const updateUserRole = async (userId, newRole) => {
      try {
        await authStore.apiRequest('http://localhost:8000/api/auth/users/role', {
          method: 'PUT',
          body: JSON.stringify({
            user_id: userId,
            role: newRole
          })
        })
        
        // Refresh users list
        await fetchUsers()
      } catch (error) {
        console.error('Error updating user role:', error)
        authStore.setError('Failed to update user role')
      }
    }

    onMounted(async () => {
      fetchTeams()
      
      // Debug authentication state
      console.log('UserProfile mounted - Auth state:', {
        user: authStore.state.user?.email,
        profile: authStore.state.profile,
        userRole: authStore.userRole,
        isAdmin: authStore.isAdmin,
        isAuthenticated: authStore.isAuthenticated
      })
      
      // Wait for authentication to be fully initialized before checking admin status
      if (authStore.state.user && authStore.state.profile && authStore.isAdmin) {
        console.log('User is admin, fetching users...')
        await fetchUsers()
      } else {
        console.log('User is not admin or profile not fully loaded, skipping admin data fetch')
      }
    })

    return {
      authStore,
      isEditing,
      saving,
      showUserManagement,
      loadingUsers,
      users,
      teams,
      editForm,
      showTeamSelection,
      roleClass,
      getRoleClass,
      formatRole,
      formatDate,
      startEditing,
      cancelEditing,
      saveChanges,
      handleLogout,
      fetchUsers,
      updateUserRole
    }
  }
}
</script>

<style scoped>
.user-profile {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

.profile-header h2 {
  margin: 0;
  color: #333;
}

.logout-btn {
  background-color: #dc3545;
  color: white;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.logout-btn:hover {
  background-color: #c82333;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.profile-content {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.profile-info {
  margin-bottom: 2rem;
}

.info-group {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid #f8f9fa;
}

.info-group label {
  font-weight: 600;
  color: #555;
  width: 150px;
  margin-right: 1rem;
}

.profile-input {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  flex: 1;
}

.profile-input:disabled {
  background-color: transparent;
  border: none;
  padding: 0.5rem 0;
}

.role-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
}

.role-admin {
  background-color: #dc3545;
  color: white;
}

.role-manager {
  background-color: #007bff;
  color: white;
}

.role-player {
  background-color: #28a745;
  color: white;
}

.role-fan {
  background-color: #6c757d;
  color: white;
}

.profile-actions {
  margin-top: 1.5rem;
}

.edit-btn, .save-btn, .cancel-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  margin-right: 0.5rem;
}

.edit-btn {
  background-color: #007bff;
  color: white;
}

.edit-btn:hover {
  background-color: #0056b3;
}

.save-btn {
  background-color: #28a745;
  color: white;
}

.save-btn:hover:not(:disabled) {
  background-color: #218838;
}

.save-btn:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.cancel-btn {
  background-color: #6c757d;
  color: white;
}

.cancel-btn:hover {
  background-color: #5a6268;
}

.team-selection {
  margin: 1rem 0;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.team-selection label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.team-selection select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 0.75rem;
  border-radius: 4px;
  margin-top: 1rem;
}

.admin-panel {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.admin-panel h3 {
  margin-top: 0;
  color: #dc3545;
}

.admin-btn {
  background-color: #dc3545;
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
}

.admin-btn:hover {
  background-color: #c82333;
}

.user-management {
  margin-top: 1.5rem;
}

.user-management h4 {
  margin-bottom: 1rem;
  color: #333;
}

.users-list {
  border: 1px solid #ddd;
  border-radius: 4px;
}

.user-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #eee;
}

.user-item:last-child {
  border-bottom: none;
}

.user-info strong {
  display: block;
  margin-bottom: 0.25rem;
}

.user-email {
  color: #666;
  font-size: 0.9rem;
  display: block;
  margin-bottom: 0.5rem;
}

.role-select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9rem;
}
</style>