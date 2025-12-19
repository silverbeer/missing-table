<template>
  <div class="login-form">
    <div class="form-container">
      <div class="logo-container">
        <img
          src="@/assets/logo-full.png"
          alt="Missing Table"
          class="login-logo"
        />
      </div>
      <h2>{{ showInviteSignup ? 'Sign Up with Invite' : 'Login' }}</h2>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="form-group">
          <label for="username">Username:</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            required
            :disabled="authStore.state.loading"
            placeholder="Enter your username"
            pattern="[a-zA-Z0-9_]{3,50}"
            title="Username must be 3-50 characters (letters, numbers, underscores only)"
            data-testid="username-input"
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
            data-testid="password-input"
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
            <p>{{ formatInviteMessage(inviteInfo) }}</p>
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

        <div v-if="showInviteSignup" class="form-group">
          <label for="email">Email (optional):</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            :disabled="authStore.state.loading"
            placeholder="Enter your email (for notifications)"
          />
        </div>

        <div
          v-if="authStore.state.error"
          class="error-message"
          data-testid="error-message"
        >
          {{ authStore.state.error }}
        </div>

        <div class="form-actions">
          <button
            type="submit"
            :disabled="authStore.state.loading"
            class="submit-btn"
            data-testid="login-button"
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

      <!-- Google Login Option (show on regular login form) -->
      <div v-if="!showInviteSignup" class="social-login">
        <div class="divider">
          <span>or continue with</span>
        </div>

        <button
          @click="handleGoogleLogin"
          :disabled="authStore.state.loading"
          class="google-btn"
          data-testid="google-login-button"
        >
          <svg class="google-icon" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          <span>Continue with Google</span>
        </button>
      </div>

      <!-- Google Sign Up Option (show on invite signup with valid invite code) -->
      <div v-if="showInviteSignup && inviteInfo" class="social-login">
        <div class="divider">
          <span>or sign up with</span>
        </div>

        <button
          @click="handleGoogleSignUp"
          :disabled="authStore.state.loading"
          class="google-btn"
          data-testid="google-signup-button"
        >
          <svg class="google-icon" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          <span>Sign up with Google</span>
        </button>
      </div>

      <div class="form-footer" data-testid="form-footer">
        <p v-if="!showInviteSignup">
          Have an invite code?
          <button
            @click="showInviteForm"
            class="link-btn"
            data-testid="signup-link"
          >
            Click here to Sign Up
          </button>
        </p>
        <p v-if="showInviteSignup">
          Already have an account?
          <button
            @click="showLoginForm"
            class="link-btn"
            data-testid="login-link"
          >
            Login
          </button>
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
import { ref, reactive, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';

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
      username: '',
      password: '',
      displayName: '',
      email: '', // Optional email for invite signups
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
          `${getApiBaseUrl()}/api/invites/validate/${form.inviteCode}`
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

    const formatInviteMessage = invite => {
      // Format user-friendly invite message without exposing internal role names
      const inviteType = invite.invite_type;
      const teamName = invite.team_name;
      const clubName = invite.club_name;

      const typeLabels = {
        club_manager: { label: 'Manager', entity: clubName },
        club_fan: { label: 'Fan', entity: clubName },
        team_manager: { label: 'Manager', entity: teamName },
        team_player: { label: 'Player', entity: teamName },
        team_fan: { label: 'Fan', entity: teamName },
      };

      const config = typeLabels[inviteType] || {
        label: '',
        entity: teamName || clubName,
      };
      return `✓ Valid ${config.label} invite for ${config.entity}`;
    };

    const fetchTeams = async () => {
      // Only fetch if not already loaded
      if (teams.value.length > 0) return;

      try {
        const response = await fetch(`${getApiBaseUrl()}/api/teams`);
        const data = await response.json();
        teams.value = data;
      } catch (error) {
        console.error('Error fetching teams:', error);
      }
    };

    // Lazy-load teams only when a team-related role is selected
    watch(selectedRole, newRole => {
      if (newRole === 'team-manager' || newRole === 'team-player') {
        fetchTeams();
      }
    });

    const handleGoogleLogin = async () => {
      authStore.clearError();
      // No invite code for login - just redirect to Google
      const result = await authStore.signInWithGoogle(null, null);
      if (!result.success) {
        console.error('Google login failed:', result.error);
      }
      // User will be redirected to Google, then back to /auth/callback
    };

    const handleGoogleSignUp = async () => {
      authStore.clearError();
      // Pass the invite code and display name through localStorage
      const result = await authStore.signInWithGoogle(
        form.inviteCode,
        form.displayName || null
      );
      if (!result.success) {
        console.error('Google sign-up failed:', result.error);
      }
      // User will be redirected to Google, then back to /auth/callback
    };

    const handleSubmit = async () => {
      authStore.clearError();

      if (isSignup.value && showInviteSignup.value) {
        const result = await authStore.signupWithInvite(
          form.username,
          form.password,
          form.displayName,
          form.inviteCode,
          form.email // Optional email
        );
        if (result.success) {
          // Role and team are already set by the backend via invite code
          // Now log the user in automatically
          const loginResult = await authStore.login(
            form.username,
            form.password
          );
          if (loginResult.success) {
            emit('login-success');
          }
        }
      } else {
        const result = await authStore.login(form.username, form.password);
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
      // Check for invite code in URL query parameter
      const urlParams = new URLSearchParams(window.location.search);
      const inviteCode = urlParams.get('code');

      if (inviteCode) {
        // Switch to invite signup form and pre-fill the code
        showInviteSignup.value = true;
        isSignup.value = true;
        form.inviteCode = inviteCode;

        // Validate the invite code automatically
        validateInviteCode();
      }
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
      formatInviteMessage,
      handleSubmit,
      handleGoogleLogin,
      handleGoogleSignUp,
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

.logo-container {
  text-align: center;
  margin-bottom: 1.5rem;
}

.login-logo {
  max-width: 280px;
  height: auto;
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

/* Social Login Styles */
.social-login {
  margin-top: 1.5rem;
}

.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1rem 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid #ddd;
}

.divider span {
  padding: 0 0.75rem;
  color: #6c757d;
  font-size: 0.875rem;
}

.google-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  color: #333;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.google-btn:hover:not(:disabled) {
  background-color: #f8f9fa;
  border-color: #ccc;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.google-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.google-icon {
  width: 20px;
  height: 20px;
}
</style>
