<template>
  <div class="profile-container">
    <div class="profile-header">
      <h2>{{ title }}</h2>
      <button @click="handleLogout" class="logout-btn">
        Logout
      </button>
    </div>

    <div v-if="authStore.state.loading" class="loading">
      Loading profile...
    </div>

    <div v-else-if="authStore.state.profile" class="profile-content">
      <!-- Basic Profile Info (shared by all) -->
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

        <div class="info-group">
          <label>Member Since:</label>
          <span>{{ formatDate(authStore.state.profile.created_at) }}</span>
        </div>

        <!-- Slot for role-specific content -->
        <slot name="profile-fields"></slot>
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

      <!-- Slot for role-specific sections -->
      <slot 
        name="profile-sections" 
        :isEditing="isEditing"
        :editForm="editForm"
        :saving="saving"
      ></slot>

      <div v-if="authStore.state.error" class="error-message">
        {{ authStore.state.error }}
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export default {
  name: 'BaseProfile',
  props: {
    title: {
      type: String,
      default: 'User Profile'
    }
  },
  emits: ['logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore()
    const isEditing = ref(false)
    const saving = ref(false)

    const editForm = reactive({
      display_name: '',
      team_id: null,
      player_number: null,
      positions: []
    })

    const roleClass = computed(() => {
      const role = authStore.state.profile?.role
      return {
        'role-admin': role === 'admin',
        'role-manager': role === 'team-manager', 
        'role-player': role === 'team-player',
        'role-fan': role === 'team-fan'
      }
    })

    const formatRole = (role) => {
      const roleMap = {
        'admin': 'Administrator',
        'team-manager': 'Team Manager',
        'team-player': 'Team Player',
        'team-fan': 'Team Fan'
      }
      return roleMap[role] || role
    }

    const formatDate = (dateString) => {
      if (!dateString) return ''
      return new Date(dateString).toLocaleDateString()
    }

    const startEditing = () => {
      if (authStore.state.profile) {
        editForm.display_name = authStore.state.profile.display_name || ''
        editForm.team_id = authStore.state.profile.team_id || null
        editForm.player_number = authStore.state.profile.player_number || null
        editForm.positions = authStore.state.profile.positions || []
      }
      isEditing.value = true
    }

    const cancelEditing = () => {
      isEditing.value = false
      editForm.display_name = ''
      editForm.team_id = null
      editForm.player_number = null
      editForm.positions = []
    }

    const saveChanges = async () => {
      try {
        saving.value = true
        
        const updateData = {
          display_name: editForm.display_name
        }

        if (editForm.team_id !== null) {
          updateData.team_id = editForm.team_id
        }

        if (editForm.player_number !== null) {
          updateData.player_number = editForm.player_number
        }

        if (editForm.positions && editForm.positions.length > 0) {
          updateData.positions = editForm.positions
        }

        await authStore.apiRequest('http://localhost:8000/api/auth/profile', {
          method: 'PUT',
          body: JSON.stringify(updateData)
        })

        // Refresh profile data
        await authStore.fetchProfile()
        isEditing.value = false
      } catch (error) {
        console.error('Error updating profile:', error)
        authStore.setError('Failed to update profile')
      } finally {
        saving.value = false
      }
    }

    const handleLogout = async () => {
      if (confirm('Are you sure you want to log out?')) {
        await authStore.logout()
        emit('logout')
      }
    }

    return {
      authStore,
      isEditing,
      saving,
      editForm,
      roleClass,
      formatRole,
      formatDate,
      startEditing,
      cancelEditing,
      saveChanges,
      handleLogout
    }
  }
}
</script>

<style scoped>
.profile-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #e5e7eb;
}

.profile-header h2 {
  color: #1f2937;
  margin: 0;
}

.logout-btn {
  background-color: #dc2626;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.logout-btn:hover {
  background-color: #b91c1c;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.profile-info {
  background-color: #f9fafb;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.info-group {
  display: flex;
  margin-bottom: 15px;
  align-items: center;
}

.info-group label {
  font-weight: 600;
  color: #374151;
  min-width: 120px;
  margin-right: 10px;
}

.profile-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
}

.profile-input:disabled {
  background-color: transparent;
  border: none;
  color: #6b7280;
}

.role-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.role-admin { background-color: #fee2e2; color: #dc2626; }
.role-manager { background-color: #dbeafe; color: #2563eb; }
.role-player { background-color: #d1fae5; color: #059669; }
.role-fan { background-color: #e5e7eb; color: #6b7280; }

.profile-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.edit-btn, .save-btn {
  background-color: #2563eb;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.edit-btn:hover, .save-btn:hover {
  background-color: #1d4ed8;
}

.cancel-btn {
  background-color: #6b7280;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.cancel-btn:hover {
  background-color: #4b5563;
}

.save-btn:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.edit-actions {
  display: flex;
  gap: 10px;
}

.error-message {
  background-color: #fef2f2;
  color: #dc2626;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #fecaca;
  margin-top: 10px;
}
</style>