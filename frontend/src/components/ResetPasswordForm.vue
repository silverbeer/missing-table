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
  width: 100%;
}

.form-hint {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 16px;
}
</style>
