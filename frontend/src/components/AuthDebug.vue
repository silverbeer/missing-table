<template>
  <div class="auth-debug">
    <h3>🔍 Auth Debug Info</h3>
    <div class="debug-info">
      <p><strong>Loading:</strong> {{ authStore.state.loading }}</p>
      <p><strong>User:</strong> {{ authStore.state.user ? 'Present' : 'None' }}</p>
      <p><strong>Session:</strong> {{ authStore.state.session ? 'Present' : 'None' }}</p>
      <p><strong>Profile:</strong> {{ authStore.state.profile ? 'Present' : 'None' }}</p>
      <p><strong>Is Authenticated:</strong> {{ authStore.isAuthenticated }}</p>
      <p><strong>User Role:</strong> {{ authStore.userRole }}</p>
      <p><strong>Error:</strong> {{ authStore.state.error || 'None' }}</p>
    </div>
    
    <div class="debug-actions">
      <button @click="clearAuth" class="debug-btn">Clear All Auth</button>
      <button @click="authStore.initialize()" class="debug-btn">Reinitialize Auth</button>
    </div>
  </div>
</template>

<script>
import { useAuthStore } from '@/stores/auth'

export default {
  name: 'AuthDebug',
  setup() {
    const authStore = useAuthStore()
    
    const clearAuth = () => {
      localStorage.clear()
      sessionStorage.clear()
      authStore.state.user = null
      authStore.state.session = null
      authStore.state.profile = null
      authStore.state.loading = false
      authStore.state.error = null
      console.log('Auth cleared')
    }
    
    return {
      authStore,
      clearAuth
    }
  }
}
</script>

<style scoped>
.auth-debug {
  background: #f8f9fa;
  border: 2px solid #dee2e6;
  border-radius: 8px;
  padding: 1rem;
  margin: 1rem 0;
  font-family: monospace;
}

.debug-info p {
  margin: 0.5rem 0;
  font-size: 0.9rem;
}

.debug-actions {
  margin-top: 1rem;
}

.debug-btn {
  background: #dc3545;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  margin-right: 0.5rem;
  cursor: pointer;
}

.debug-btn:hover {
  background: #c82333;
}
</style>