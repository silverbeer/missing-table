<template>
  <div class="admin-cache">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-semibold text-gray-900">Cache Management</h2>
      <button
        @click="fetchCacheStats"
        :disabled="loading"
        class="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
      >
        {{ loading ? 'Loading...' : 'Refresh' }}
      </button>
    </div>

    <!-- Error Message -->
    <div
      v-if="error"
      class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
    >
      {{ error }}
    </div>

    <!-- Cache Disabled -->
    <div
      v-if="!cacheStats.enabled && !loading"
      class="text-center py-8 text-gray-500"
    >
      <div class="text-4xl mb-2">🚫</div>
      <p>{{ cacheStats.message || 'Cache is disabled' }}</p>
    </div>

    <!-- Cache Stats -->
    <div v-else-if="cacheStats.enabled">
      <!-- Summary -->
      <div class="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-2xl font-bold text-blue-700">{{
              cacheStats.total_keys
            }}</span>
            <span class="text-blue-600 ml-2">total cached items</span>
          </div>
          <button
            @click="clearAllCache"
            :disabled="clearing || cacheStats.total_keys === 0"
            class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ clearing ? 'Clearing...' : 'Clear All Cache' }}
          </button>
        </div>
      </div>

      <!-- Cache Groups -->
      <div class="space-y-4">
        <div
          v-for="(group, type) in cacheStats.groups"
          :key="type"
          class="border border-gray-200 rounded-lg overflow-hidden"
        >
          <div
            class="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200"
          >
            <div class="flex items-center space-x-3">
              <span class="text-lg">{{ getCacheIcon(type) }}</span>
              <span class="font-medium text-gray-900 capitalize">{{
                type
              }}</span>
              <span
                class="px-2 py-0.5 text-xs bg-gray-200 text-gray-700 rounded-full"
              >
                {{ group.count }} items
              </span>
            </div>
            <button
              @click="clearCacheByType(type)"
              :disabled="clearing"
              class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
            >
              Clear
            </button>
          </div>

          <!-- Expandable Keys List -->
          <div class="px-4 py-2 max-h-40 overflow-y-auto bg-white">
            <div
              v-for="key in group.keys.slice(0, 10)"
              :key="key"
              class="text-xs text-gray-500 font-mono py-0.5 truncate"
              :title="key"
            >
              {{ key }}
            </div>
            <div
              v-if="group.keys.length > 10"
              class="text-xs text-gray-400 py-1"
            >
              ... and {{ group.keys.length - 10 }} more
            </div>
          </div>
        </div>
      </div>

      <!-- No Cache -->
      <div
        v-if="Object.keys(cacheStats.groups).length === 0"
        class="text-center py-8 text-gray-500"
      >
        <div class="text-4xl mb-2">✨</div>
        <p>Cache is empty</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="text-center py-8 text-gray-500">
      Loading cache stats...
    </div>

    <!-- Success Message -->
    <div
      v-if="successMessage"
      class="mt-4 p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm"
    >
      {{ successMessage }}
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

export default {
  name: 'AdminCache',
  setup() {
    const authStore = useAuthStore();
    const loading = ref(false);
    const clearing = ref(false);
    const error = ref(null);
    const successMessage = ref(null);
    const cacheStats = ref({ enabled: false, total_keys: 0, groups: {} });

    const getCacheIcon = type => {
      const icons = {
        playoffs: '🏆',
        matches: '⚽',
        players: '👤',
        clubs: '🏢',
        teams: '👥',
        standings: '📊',
        rosters: '📋',
      };
      return icons[type] || '📦';
    };

    const fetchCacheStats = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/cache`,
          { method: 'GET' }
        );
        cacheStats.value = data;
      } catch (err) {
        error.value = err.message || 'Failed to fetch cache stats';
      } finally {
        loading.value = false;
      }
    };

    const clearAllCache = async () => {
      if (!confirm('Are you sure you want to clear ALL cache?')) return;

      clearing.value = true;
      error.value = null;
      successMessage.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/cache`,
          { method: 'DELETE' }
        );
        successMessage.value = `Cleared ${data.deleted} cache entries`;
        await fetchCacheStats();
        setTimeout(() => (successMessage.value = null), 3000);
      } catch (err) {
        error.value = err.message || 'Failed to clear cache';
      } finally {
        clearing.value = false;
      }
    };

    const clearCacheByType = async type => {
      clearing.value = true;
      error.value = null;
      successMessage.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/cache/${type}`,
          { method: 'DELETE' }
        );
        successMessage.value = `Cleared ${data.deleted} ${type} cache entries`;
        await fetchCacheStats();
        setTimeout(() => (successMessage.value = null), 3000);
      } catch (err) {
        error.value = err.message || `Failed to clear ${type} cache`;
      } finally {
        clearing.value = false;
      }
    };

    onMounted(fetchCacheStats);

    return {
      loading,
      clearing,
      error,
      successMessage,
      cacheStats,
      getCacheIcon,
      fetchCacheStats,
      clearAllCache,
      clearCacheByType,
    };
  },
};
</script>
