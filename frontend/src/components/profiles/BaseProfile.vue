<template>
  <div class="profile-container">
    <div class="profile-header">
      <h2>{{ title }}</h2>
      <button @click="handleLogout" class="logout-btn">Logout</button>
    </div>

    <div v-if="authStore.state.loading" class="loading">Loading profile...</div>

    <div v-else-if="authStore.state.profile" class="profile-content">
      <!-- Basic Profile Info (shared by all) -->
      <div class="profile-info">
        <div class="info-group">
          <label>Username:</label>
          <span>{{
            authStore.state.profile?.username || authStore.state.user?.username
          }}</span>
        </div>

        <div class="info-group">
          <label>Email:</label>
          <input
            v-model="editForm.email"
            type="email"
            :disabled="!isEditing"
            class="profile-input"
            :class="{
              'input-error': emailError && isEditing,
              'input-valid':
                !emailError &&
                editForm.email &&
                editForm.email.trim() &&
                isEditing,
            }"
            :placeholder="
              authStore.state.profile?.email || 'Enter email (optional)'
            "
            @input="validateEmail"
            @blur="validateEmail"
          />
          <span v-if="emailError && isEditing" class="field-error">{{
            emailError
          }}</span>
          <span
            v-else-if="
              isEditing &&
              editForm.email &&
              editForm.email.trim() &&
              !emailError
            "
            class="field-success"
            >✓ Valid email</span
          >
          <span v-else-if="isEditing" class="field-hint"
            >Optional - leave blank if you prefer</span
          >
        </div>

        <div class="info-group">
          <label>Display Name:</label>
          <input
            v-model="editForm.display_name"
            type="text"
            :disabled="!isEditing"
            class="profile-input"
            :placeholder="
              authStore.state.profile?.display_name || 'Enter display name'
            "
          />
        </div>

        <div class="info-group">
          <label>Role:</label>
          <span class="role-badge" :class="roleClass">
            {{ displayRole }}
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
        <button v-if="!isEditing" @click="startEditing" class="edit-btn">
          Edit Profile
        </button>

        <div v-else class="edit-actions">
          <button
            @click="saveChanges"
            :disabled="saving || !!emailError"
            class="save-btn"
            :title="emailError ? 'Fix email errors before saving' : ''"
          >
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
          <button @click="cancelEditing" class="cancel-btn">Cancel</button>
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
import { ref, reactive, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'BaseProfile',
  props: {
    title: {
      type: String,
      default: 'User Profile',
    },
  },
  emits: ['logout'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const isEditing = ref(false);
    const saving = ref(false);
    const emailError = ref('');

    const editForm = reactive({
      display_name: '',
      email: '',
      team_id: null,
      player_number: null,
      positions: [],
    });

    const roleClass = computed(() => {
      const role = authStore.state.profile?.role;
      return {
        'role-admin': role === 'admin',
        'role-manager': role === 'team-manager',
        'role-player': role === 'team-player',
        'role-fan': role === 'team-fan',
      };
    });

    const formatRole = role => {
      const roleMap = {
        admin: 'Administrator',
        'team-manager': 'Team Manager',
        'team-player': 'Team Player',
        'team-fan': 'Team Fan',
      };
      return roleMap[role] || role;
    };

    const displayRole = computed(() => {
      const role = authStore.state.profile?.role;
      const hasClub = !!authStore.state.profile?.club_id;
      const hasTeam = !!authStore.state.profile?.team_id;

      // If user has club_id, they're managing a club
      if (role === 'team-manager' && hasClub) {
        return 'Club Manager';
      }
      // If user has team_id, they're managing a single team
      if (role === 'team-manager' && hasTeam) {
        return 'Team Manager';
      }
      // Otherwise use default role formatting
      return formatRole(role);
    });

    const formatDate = dateString => {
      if (!dateString) return '';
      return new Date(dateString).toLocaleDateString();
    };

    const validateEmail = () => {
      emailError.value = '';

      if (!editForm.email || editForm.email.trim() === '') {
        // Empty email is allowed
        return true;
      }

      // Email format validation
      const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!emailPattern.test(editForm.email)) {
        emailError.value =
          '⚠️ Invalid email format. Please enter a valid email address (e.g., user@example.com)';
        return false;
      }

      return true;
    };

    const initializeEditForm = () => {
      if (authStore.state.profile) {
        editForm.display_name = authStore.state.profile.display_name || '';
        editForm.email = authStore.state.profile.email || '';
        editForm.team_id = authStore.state.profile.team_id || null;
        editForm.player_number = authStore.state.profile.player_number || null;
        editForm.positions = authStore.state.profile.positions || [];
      }
    };

    const startEditing = () => {
      initializeEditForm();
      emailError.value = '';
      authStore.clearError();
      isEditing.value = true;
      // Validate email on start if there's already a value
      if (editForm.email) {
        validateEmail();
      }
    };

    const cancelEditing = () => {
      isEditing.value = false;
      emailError.value = '';
      authStore.clearError();
      editForm.display_name = '';
      editForm.email = '';
      editForm.team_id = null;
      editForm.player_number = null;
      editForm.positions = [];
    };

    const saveChanges = async () => {
      try {
        // Validate email before submitting
        if (!validateEmail()) {
          saving.value = false;
          return;
        }

        saving.value = true;
        authStore.clearError();

        const updateData = {
          display_name: editForm.display_name,
          email: editForm.email,
        };

        if (editForm.team_id !== null) {
          updateData.team_id = editForm.team_id;
        }

        if (editForm.player_number !== null) {
          updateData.player_number = editForm.player_number;
        }

        if (editForm.positions && editForm.positions.length > 0) {
          updateData.positions = editForm.positions;
        }

        await authStore.apiRequest(`${getApiBaseUrl()}/api/auth/profile`, {
          method: 'PUT',
          body: JSON.stringify(updateData),
        });

        // Refresh profile data
        await authStore.fetchProfile();
        isEditing.value = false;
      } catch (error) {
        console.error('Error updating profile:', error);
        // Extract specific error message from backend
        const errorMessage = error?.message || 'Failed to update profile';
        authStore.setError(errorMessage);
      } finally {
        saving.value = false;
      }
    };

    const handleLogout = async () => {
      if (confirm('Are you sure you want to log out?')) {
        await authStore.logout();
        emit('logout');
      }
    };

    // Initialize edit form when component mounts
    onMounted(() => {
      initializeEditForm();
    });

    // Watch for profile changes and update edit form
    watch(
      () => authStore.state.profile,
      () => {
        initializeEditForm();
      },
      { immediate: true }
    );

    return {
      authStore,
      isEditing,
      saving,
      editForm,
      emailError,
      roleClass,
      displayRole,
      formatRole,
      formatDate,
      validateEmail,
      startEditing,
      cancelEditing,
      saveChanges,
      handleLogout,
    };
  },
};
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

.profile-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.edit-btn,
.save-btn {
  background-color: #2563eb;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.edit-btn:hover,
.save-btn:hover {
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

.field-hint {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  font-style: italic;
}

.field-error {
  display: block;
  font-size: 13px;
  color: #dc2626;
  margin-top: 4px;
  font-weight: 500;
}

.field-success {
  display: block;
  font-size: 13px;
  color: #059669;
  margin-top: 4px;
  font-weight: 500;
}

.input-error {
  border-color: #dc2626 !important;
  background-color: #fef2f2;
}

.input-error:focus {
  outline: 2px solid #dc2626;
  outline-offset: 2px;
}

.input-valid {
  border-color: #059669 !important;
  background-color: #f0fdf4;
}

.input-valid:focus {
  outline: 2px solid #059669;
  outline-offset: 2px;
}
</style>
