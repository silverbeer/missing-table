<template>
  <div class="login-form">
    <div class="form-container">
      <div class="logo-container">
        <img :src="logoSrc" alt="Missing Table" class="login-logo" />
        <p class="login-tagline">
          {{
            showInviteSignup ? 'Create your account' : 'Sign in to your account'
          }}
        </p>
      </div>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="form-group">
          <label for="username">Username:</label>
          <input
            id="username"
            ref="usernameInput"
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
          <label for="email">Email:</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            required
            :disabled="authStore.state.loading"
            placeholder="Enter your email (for password recovery)"
          />
        </div>

        <div
          v-if="authStore.state.error"
          class="error-message"
          data-testid="error-message"
        >
          <span>{{ authStore.state.error }}</span>
          <p v-if="showInviteSignup" class="error-support-line">
            Stuck? Email
            <SupportEmailLink
              :subject="supportSubjectForError"
              :body="supportBodyForError"
            />
            and we'll help.
          </p>
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
        <p v-if="!showInviteSignup">
          <button
            @click="$emit('show-forgot-password')"
            class="link-btn"
            data-testid="forgot-password-link"
          >
            Forgot password?
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
        <p
          v-if="showInviteSignup"
          class="support-line"
          data-testid="invite-support-line"
        >
          Need help with your invite? Contact
          <SupportEmailLink
            :subject="supportSubjectForInvite"
            :body="supportBodyForInvite"
          />.
        </p>
      </div>

      <!-- Role Selection (after successful signup) -->
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
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useTheme } from '@/composables/useTheme';
import { getApiBaseUrl } from '../config/api';
import SupportEmailLink from '@/components/SupportEmailLink.vue';
import logoFull from '@/assets/logo-full.png';
import logoFullDark from '@/assets/logo-full-dark.png';

export default {
  name: 'LoginForm',
  components: { SupportEmailLink },
  emits: ['login-success', 'show-forgot-password'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const { isDark } = useTheme();
    const logoSrc = computed(() => (isDark.value ? logoFullDark : logoFull));
    const isSignup = ref(false);
    const showInviteSignup = ref(false);
    const showRoleSelection = ref(false);
    const selectedRole = ref('team-fan');
    const selectedTeamId = ref('');
    const teams = ref([]);
    const inviteInfo = ref(null);
    const usernameInput = ref(null);

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
          // Roster-claim preflight (SB-287): the invite is real but its
          // roster spot can't be claimed - block before the user fills
          // out the form.
          if (data.claimable === false) {
            authStore.setError(
              data.claim_reason || 'This invite can no longer be used.'
            );
          }
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
      } else {
        nextTick(() => usernameInput.value?.focus());
      }
    });

    const supportSubjectForInvite = computed(() =>
      form.inviteCode
        ? `Help with invite code ${form.inviteCode}`
        : 'Help with my Missing Table invite'
    );
    const supportBodyForInvite = computed(() => {
      const lines = ['Hi support team,', '', 'I need help with my invite.'];
      if (form.inviteCode) lines.push('', `Invite code: ${form.inviteCode}`);
      if (form.email) lines.push(`Email on invite: ${form.email}`);
      return lines.join('\n');
    });
    const supportSubjectForError = computed(
      () => supportSubjectForInvite.value
    );
    const supportBodyForError = computed(() => {
      const lines = ['Hi support team,', '', 'I hit an error during signup:'];
      if (authStore.state.error) lines.push('', authStore.state.error);
      if (form.inviteCode) lines.push('', `Invite code: ${form.inviteCode}`);
      if (form.email) lines.push(`Email on invite: ${form.email}`);
      return lines.join('\n');
    });

    return {
      authStore,
      logoSrc,
      isSignup,
      showInviteSignup,
      form,
      usernameInput,
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
      supportSubjectForInvite,
      supportBodyForInvite,
      supportSubjectForError,
      supportBodyForError,
    };
  },
};
</script>

<style scoped>
.login-form {
  display: flex;
  flex-direction: column;
}

.form-container {
  padding: 2rem 2rem 2rem;
  background: rgb(var(--color-card));
}

.logo-container {
  text-align: center;
  margin-bottom: 1.75rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgb(var(--color-line));
}

.login-logo {
  max-width: 220px;
  height: auto;
}

.login-tagline {
  margin: 0.75rem 0 0;
  color: rgb(var(--color-fg-muted));
  font-size: 0.875rem;
  font-weight: 500;
}

.auth-form {
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1.1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-weight: 600;
  font-size: 0.875rem;
  color: rgb(var(--color-fg));
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  font-size: 0.95rem;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  box-sizing: border-box;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #1e40af;
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.15);
  background: rgb(var(--color-card));
}

.form-group input:disabled {
  background-color: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg-muted));
  cursor: not-allowed;
}

.error-message {
  background-color: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
  padding: 0.75rem;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.error-support-line {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: #7f1d1d;
}

.support-line {
  margin-top: 0.75rem;
  font-size: 0.85rem;
  color: rgb(var(--color-fg-muted));
}

.form-actions {
  margin-top: 1.25rem;
}

.submit-btn {
  width: 100%;
  background-color: #1e40af;
  color: white;
  padding: 0.75rem;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
  letter-spacing: 0.01em;
}

.submit-btn:hover:not(:disabled) {
  background-color: #1a3793;
}

.submit-btn:disabled {
  background-color: rgb(var(--color-fg-muted));
  cursor: not-allowed;
}

.form-footer {
  text-align: center;
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid rgb(var(--color-line));
  font-size: 0.875rem;
  color: rgb(var(--color-fg-muted));
}

.form-footer p {
  margin: 0.35rem 0;
}

.link-btn {
  background: none;
  border: none;
  color: #1e40af;
  cursor: pointer;
  text-decoration: underline;
  font-size: inherit;
  font-weight: 500;
}

.link-btn:hover {
  color: #1a3793;
}

.role-selection {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgb(var(--color-line));
}

.role-selection h3 {
  margin-bottom: 1rem;
  color: rgb(var(--color-fg));
  font-size: 1rem;
  font-weight: 700;
}

.role-options {
  margin-bottom: 1rem;
}

.role-option {
  display: block;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  cursor: pointer;
  transition:
    background-color 0.15s,
    border-color 0.15s;
}

.role-option:hover {
  background-color: rgb(var(--color-surface-alt));
  border-color: #1e40af;
}

.role-option input[type='radio'] {
  margin-right: 0.5rem;
  accent-color: #1e40af;
}

.role-option span {
  font-weight: 600;
  display: block;
  color: rgb(var(--color-fg));
  font-size: 0.9rem;
}

.role-option small {
  color: rgb(var(--color-fg-muted));
  font-size: 0.8rem;
}

.team-selection {
  margin: 1rem 0;
}

.team-selection label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  color: rgb(var(--color-fg));
}

.invite-info {
  margin-top: 0.5rem;
  padding: 0.65rem 0.75rem;
  background-color: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  font-size: 0.875rem;
}

.invite-info p {
  margin: 0;
  color: #166534;
  font-weight: 500;
}

/* Social Login */
.social-login {
  margin-top: 1.25rem;
}

.divider {
  display: flex;
  align-items: center;
  margin: 1rem 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid rgb(var(--color-line));
}

.divider span {
  padding: 0 0.75rem;
  color: rgb(var(--color-fg-muted));
  font-size: 0.8rem;
  white-space: nowrap;
}

.google-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.7rem 1rem;
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  background-color: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.google-btn:hover:not(:disabled) {
  background-color: rgb(var(--color-surface-alt));
  border-color: rgb(var(--color-line));
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.google-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.google-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* Navy links unreadable on dark card -- lighten in dark mode (SB-159). */
:global(.dark) .link-btn {
  color: #779edb;
}
:global(.dark) .link-btn:hover {
  color: #aac3ea;
}
</style>
