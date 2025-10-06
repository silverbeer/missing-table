<template>
  <div class="login-form">
    <div class="form-container">
      <h2>{{ showInviteSignup ? 'Sign Up with Invite' : 'Login' }}</h2>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="form-group">
          <label for="email">Email:</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            required
            :disabled="authStore.state.loading"
            placeholder="Enter your email"
          />
        </div>

        <div class="form-group">
          <label for="password">Password:</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            required
            :disabled="authStore.state.loading"
            placeholder="Enter your password"
            minlength="6"
          />
        </div>

        <div v-if="showInviteSignup" class="form-group">
          <label for="inviteCode">Invite Code:</label>
          <input
            id="inviteCode"
            v-model="form.inviteCode"
            type="text"
            required
            :disabled="authStore.state.loading"
            placeholder="Enter your invite code"
            @blur="validateInviteCode"
          />
          <div v-if="inviteInfo" class="invite-info">
            <p>
              ✓ Valid invite for <strong>{{ inviteInfo.team_name }}</strong>
            </p>
            <p>
              Role:
              <strong>{{ inviteInfo.invite_type.replace('_', ' ') }}</strong>
            </p>
          </div>
        </div>

        <div v-if="showInviteSignup" class="form-group">
          <label for="displayName">Display Name (optional):</label>
          <input
            id="displayName"
            v-model="form.displayName"
            type="text"
            :disabled="authStore.state.loading"
            placeholder="Enter your display name"
          />
        </div>

        <div v-if="authStore.state.error" class="error-message">
          {{ authStore.state.error }}
        </div>

        <div class="form-actions">
          <button
            type="submit"
            :disabled="authStore.state.loading"
            class="submit-btn"
          >
            {{
              authStore.state.loading
                ? 'Processing...'
                : isSignup
                  ? 'Sign Up'
                  : 'Login'
            }}
          </button>
        </div>
      </form>

      <div class="form-footer">
        <p v-if="!showInviteSignup">
          Have an invite code?
          <button @click="showInviteForm" class="link-btn">
            Click here to Sign Up
          </button>
        </p>
        <p v-if="showInviteSignup">
          Already have an account?
          <button @click="showLoginForm" class="link-btn">Login</button>
        </p>
      </div>

      <!-- Role Selection for Admins (after successful signup) -->
      <div v-if="showRoleSelection" class="role-selection">
        <h3>Select Your Role</h3>
        <div class="role-options">
          <label class="role-option">
            <input v-model="selectedRole" type="radio" value="team-fan" />
            <span>Team Fan</span>
            <small>View games and league tables</small>
          </label>
          <label class="role-option">
            <input v-model="selectedRole" type="radio" value="team-player" />
            <span>Team Player</span>
            <small>View your team's information</small>
          </label>
          <label class="role-option">
            <input v-model="selectedRole" type="radio" value="team-manager" />
            <span>Team Manager</span>
            <small>Manage your team and games</small>
          </label>
        </div>

        <div
          v-if="
            selectedRole === 'team-manager' || selectedRole === 'team-player'
          "
          class="team-selection"
        >
          <label for="teamSelect">Select Your Team:</label>
          <select id="teamSelect" v-model="selectedTeamId" required>
            <option value="">Choose a team...</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }} ({{ team.city }})
            </option>
          </select>
        </div>

        <button
          @click="completeProfile"
          :disabled="!selectedRole"
          class="submit-btn"
        >
          Complete Profile
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'LoginForm',
  emits: ['login-success'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const isSignup = ref(false);
    const showInviteSignup = ref(false);
    const showRoleSelection = ref(false);
    const selectedRole = ref('team-fan');
    const selectedTeamId = ref('');
    const teams = ref([]);
    const inviteInfo = ref(null);

    const form = reactive({
      email: '',
      password: '',
      displayName: '',
      inviteCode: '',
    });

    const showInviteForm = () => {
      showInviteSignup.value = true;
      isSignup.value = true;
      authStore.clearError();
      showRoleSelection.value = false;
    };

    const showLoginForm = () => {
      showInviteSignup.value = false;
      isSignup.value = false;
      authStore.clearError();
      showRoleSelection.value = false;
    };

    const validateInviteCode = async () => {
      if (!form.inviteCode || form.inviteCode.length < 8) {
        inviteInfo.value = null;
        return;
      }

      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/invites/validate/${form.inviteCode}`
        );

        if (response.ok) {
          const data = await response.json();
          inviteInfo.value = data;
        } else {
          inviteInfo.value = null;
          authStore.setError('Invalid or expired invite code');
        }
      } catch (error) {
        console.error('Error validating invite:', error);
        inviteInfo.value = null;
      }
    };

    const fetchTeams = async () => {
      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`
        );
        const data = await response.json();
        teams.value = data;
      } catch (error) {
        console.error('Error fetching teams:', error);
      }
    };

    const handleSubmit = async () => {
      authStore.clearError();

      if (isSignup.value && showInviteSignup.value) {
        const result = await authStore.signupWithInvite(
          form.email,
          form.password,
          form.displayName,
          form.inviteCode
        );
        if (result.success) {
          // Role and team are already set by the backend via invite code
          // Now log the user in automatically
          const loginResult = await authStore.login(form.email, form.password);
          if (loginResult.success) {
            emit('login-success');
          }
        }
      } else {
        const result = await authStore.login(form.email, form.password);
        if (result.success) {
          emit('login-success');
        }
      }
    };

    const completeProfile = async () => {
      try {
        const updates = { role: selectedRole.value };
        if (selectedTeamId.value) {
          updates.team_id = selectedTeamId.value;
        }

        const result = await authStore.updateProfile(updates);
        if (result.success) {
          emit('login-success');
        }
      } catch (error) {
        authStore.setError('Failed to update profile');
      }
    };

    onMounted(() => {
      fetchTeams();
    });

    return {
      authStore,
      isSignup,
      showInviteSignup,
      form,
      showRoleSelection,
      selectedRole,
      selectedTeamId,
      teams,
      inviteInfo,
      showInviteForm,
      showLoginForm,
      validateInviteCode,
      handleSubmit,
      completeProfile,
    };
  },
};
</script>

<style scoped>
.login-form {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
  padding: 20px;
}

.form-container {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

.form-container h2 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: #333;
}

.auth-form {
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: #555;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  transition: border-color 0.2s;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}

.form-group input:disabled {
  background-color: #f8f9fa;
  cursor: not-allowed;
}

.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 0.75rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.form-actions {
  margin-top: 1.5rem;
}

.submit-btn {
  width: 100%;
  background-color: #007bff;
  color: white;
  padding: 0.75rem;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.submit-btn:hover:not(:disabled) {
  background-color: #0056b3;
}

.submit-btn:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.form-footer {
  text-align: center;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
}

.link-btn {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  text-decoration: underline;
  font-size: inherit;
}

.link-btn:hover {
  color: #0056b3;
}

.role-selection {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #eee;
}

.role-selection h3 {
  margin-bottom: 1rem;
  color: #333;
}

.role-options {
  margin-bottom: 1rem;
}

.role-option {
  display: block;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.role-option:hover {
  background-color: #f8f9fa;
}

.role-option input[type='radio'] {
  margin-right: 0.5rem;
}

.role-option span {
  font-weight: 600;
  display: block;
}

.role-option small {
  color: #666;
  font-size: 0.85rem;
}

.team-selection {
  margin: 1rem 0;
}

.team-selection label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.invite-info {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background-color: #d4edda;
  border: 1px solid #c3e6cb;
  border-radius: 4px;
  font-size: 0.9rem;
}

.invite-info p {
  margin: 0.25rem 0;
  color: #155724;
}

.invite-info strong {
  color: #0f4c20;
}
</style>
