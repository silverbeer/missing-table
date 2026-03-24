<template>
  <div class="forgot-password-form">
    <div class="form-container">
      <div class="logo-container">
        <img
          src="@/assets/logo-full.png"
          alt="Missing Table"
          class="login-logo"
        />
      </div>

      <!-- Step 1: enter username or email -->
      <template v-if="step === 'identifier'">
        <h2>Forgot Password</h2>
        <p class="form-hint">
          Enter your username or email address and we'll send you a reset link.
        </p>
        <form @submit.prevent="submitIdentifier" class="auth-form">
          <div class="form-group">
            <label for="fp-identifier">Username or Email:</label>
            <input
              id="fp-identifier"
              v-model="identifier"
              type="text"
              required
              :disabled="authStore.state.loading"
              placeholder="Your username or email"
              data-testid="fp-identifier-input"
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
              {{ authStore.state.loading ? 'Sending…' : 'Send Reset Link' }}
            </button>
          </div>
        </form>
      </template>

      <!-- Step 2: no email on file — collect it -->
      <template v-else-if="step === 'provide-email'">
        <h2>Add Your Email</h2>
        <p class="form-hint">
          Your account doesn't have an email address on file. Enter one below
          and we'll send your reset link there.
        </p>
        <form @submit.prevent="submitEmail" class="auth-form">
          <div class="form-group">
            <label for="fp-email">Email Address:</label>
            <input
              id="fp-email"
              v-model="email"
              type="email"
              required
              :disabled="authStore.state.loading"
              placeholder="you@example.com"
              data-testid="fp-email-input"
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
              {{ authStore.state.loading ? 'Sending…' : 'Send Reset Link' }}
            </button>
          </div>
        </form>
      </template>

      <!-- Step 3: check your email -->
      <template v-else-if="step === 'check-email'">
        <h2>Check Your Email</h2>
        <p class="form-hint">
          If an account exists for <strong>{{ identifier }}</strong
          >, a password reset link has been sent. The link expires in 1 hour.
        </p>
        <p class="form-hint">
          Didn't receive it? Check your spam folder or try again.
        </p>
      </template>

      <div class="form-footer">
        <button @click="$emit('back-to-login')" class="link-btn">
          ← Back to Login
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'ForgotPasswordForm',
  emits: ['back-to-login'],
  setup() {
    const authStore = useAuthStore();
    const step = ref('identifier');
    const identifier = ref('');
    const email = ref('');

    const submitIdentifier = async () => {
      authStore.clearError();
      const result = await authStore.requestPasswordReset(identifier.value);
      if (!result.success) return;

      if (result.needsEmail) {
        step.value = 'provide-email';
      } else {
        step.value = 'check-email';
      }
    };

    const submitEmail = async () => {
      authStore.clearError();
      const result = await authStore.requestPasswordReset(
        identifier.value,
        email.value
      );
      if (!result.success) return;
      step.value = 'check-email';
    };

    return {
      authStore,
      step,
      identifier,
      email,
      submitIdentifier,
      submitEmail,
    };
  },
};
</script>

<style scoped>
.forgot-password-form {
  width: 100%;
}

.form-hint {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 16px;
}

/* Reuse LoginForm styles via shared classes */
.form-container,
.form-group,
.submit-btn,
.error-message,
.form-footer,
.link-btn,
.auth-form,
.logo-container,
.login-logo {
  /* Inherit from global login styles */
}
</style>
