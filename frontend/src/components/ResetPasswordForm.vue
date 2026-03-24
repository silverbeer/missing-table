<template>
  <div class="reset-password-form">
    <div class="form-container">
      <div class="logo-container">
        <img
          src="@/assets/logo-full.png"
          alt="Missing Table"
          class="login-logo"
        />
      </div>

      <template v-if="!success">
        <h2>Set New Password</h2>

        <form @submit.prevent="handleSubmit" class="auth-form">
          <div class="form-group">
            <label for="rp-password">New Password:</label>
            <input
              id="rp-password"
              v-model="newPassword"
              type="password"
              required
              minlength="6"
              :disabled="authStore.state.loading"
              placeholder="At least 6 characters"
              data-testid="rp-password-input"
            />
          </div>

          <div class="form-group">
            <label for="rp-confirm">Confirm Password:</label>
            <input
              id="rp-confirm"
              v-model="confirmPassword"
              type="password"
              required
              minlength="6"
              :disabled="authStore.state.loading"
              placeholder="Re-enter your password"
              data-testid="rp-confirm-input"
            />
          </div>

          <div v-if="mismatchError" class="error-message">
            Passwords do not match.
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
              {{ authStore.state.loading ? 'Saving…' : 'Save New Password' }}
            </button>
          </div>
        </form>
      </template>

      <template v-else>
        <h2>Password Updated</h2>
        <p class="form-hint">Your password has been changed successfully.</p>
        <div class="form-actions">
          <button @click="$emit('back-to-login')" class="submit-btn">
            Go to Login
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'ResetPasswordForm',
  props: {
    token: {
      type: String,
      required: true,
    },
  },
  emits: ['back-to-login'],
  setup(props) {
    const authStore = useAuthStore();
    const newPassword = ref('');
    const confirmPassword = ref('');
    const mismatchError = ref(false);
    const success = ref(false);

    const handleSubmit = async () => {
      mismatchError.value = false;
      authStore.clearError();

      if (newPassword.value !== confirmPassword.value) {
        mismatchError.value = true;
        return;
      }

      const result = await authStore.resetPassword(
        props.token,
        newPassword.value
      );
      if (result.success) {
        success.value = true;
      }
    };

    return {
      authStore,
      newPassword,
      confirmPassword,
      mismatchError,
      success,
      handleSubmit,
    };
  },
};
</script>

<style scoped>
.reset-password-form {
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

.form-hint {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 16px;
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

.form-group input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
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
</style>
