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
</style>
