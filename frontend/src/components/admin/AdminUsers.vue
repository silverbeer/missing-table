<template>
  <div class="admin-users">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-semibold text-gray-900">User Login Activity</h2>
      <button
        @click="activeTab === 'users' ? fetchUsers() : fetchLoginEvents()"
        :disabled="loading"
        class="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
      >
        {{ loading ? 'Loading...' : 'Refresh' }}
      </button>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
    >
      {{ error }}
    </div>

    <!-- Tabs -->
    <div class="mb-4 border-b border-gray-200">
      <nav class="flex space-x-4">
        <button
          @click="
            activeTab = 'users';
            fetchUsers();
          "
          :class="[
            activeTab === 'users'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-500 hover:text-gray-700',
            'pb-2 text-sm font-medium',
          ]"
        >
          Users ({{ userTotal }})
        </button>
        <button
          @click="
            activeTab = 'events';
            fetchLoginEvents();
          "
          :class="[
            activeTab === 'events'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-500 hover:text-gray-700',
            'pb-2 text-sm font-medium',
          ]"
        >
          Login History ({{ eventTotal }})
        </button>
      </nav>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'">
      <div v-if="loading" class="text-center py-8 text-gray-500">
        Loading users...
      </div>
      <div
        v-else-if="users.length === 0"
        class="text-center py-8 text-gray-500"
      >
        No users found.
      </div>
      <div v-else class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="text-left text-gray-500 border-b border-gray-200">
              <th class="pb-2 pr-4 font-medium">Username</th>
              <th class="pb-2 pr-4 font-medium">Display Name</th>
              <th class="pb-2 pr-4 font-medium">Role</th>
              <th class="pb-2 pr-4 font-medium">Last Login</th>
              <th class="pb-2 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50">
              <td class="py-2 pr-4 font-mono text-gray-900">
                {{ user.username }}
              </td>
              <td class="py-2 pr-4 text-gray-700">
                {{ user.display_name || '—' }}
              </td>
              <td class="py-2 pr-4">
                <span :class="roleBadgeClass(user.role)">{{
                  user.role || 'user'
                }}</span>
              </td>
              <td class="py-2 pr-4 text-gray-600">
                <span v-if="user.last_login_at">
                  <span
                    :class="
                      user.last_login_success
                        ? 'text-green-600'
                        : 'text-red-500'
                    "
                    class="mr-1"
                    >{{ user.last_login_success ? '✓' : '✗' }}</span
                  >
                  {{ formatDate(user.last_login_at) }}
                </span>
                <span v-else class="text-gray-400 italic">Never</span>
              </td>
              <td class="py-2 text-gray-500">
                {{ formatDate(user.created_at) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Login Events Tab -->
    <div v-if="activeTab === 'events'">
      <!-- Filters -->
      <div class="flex flex-wrap gap-3 mb-4">
        <input
          v-model="filterUsername"
          @input="debouncedFetch"
          type="text"
          placeholder="Filter by username..."
          class="px-3 py-1.5 text-sm border border-gray-300 rounded w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          v-model="filterSuccess"
          @change="fetchLoginEvents"
          class="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All results</option>
          <option value="true">Success only</option>
          <option value="false">Failures only</option>
        </select>
      </div>

      <div v-if="loading" class="text-center py-8 text-gray-500">
        Loading events...
      </div>
      <div
        v-else-if="events.length === 0"
        class="text-center py-8 text-gray-500"
      >
        No login events found.
      </div>
      <div v-else>
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="text-left text-gray-500 border-b border-gray-200">
                <th class="pb-2 pr-4 font-medium">Time</th>
                <th class="pb-2 pr-4 font-medium">Username</th>
                <th class="pb-2 pr-4 font-medium">Result</th>
                <th class="pb-2 pr-4 font-medium">IP Address</th>
                <th class="pb-2 font-medium">Role</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="ev in events" :key="ev.id" class="hover:bg-gray-50">
                <td class="py-2 pr-4 text-gray-600 whitespace-nowrap">
                  {{ formatDate(ev.created_at) }}
                </td>
                <td class="py-2 pr-4 font-mono text-gray-900">
                  {{ ev.username }}
                </td>
                <td class="py-2 pr-4">
                  <span
                    v-if="ev.success"
                    class="text-green-700 bg-green-50 px-2 py-0.5 rounded text-xs font-medium"
                    >Success</span
                  >
                  <span
                    v-else
                    class="text-red-700 bg-red-50 px-2 py-0.5 rounded text-xs font-medium"
                  >
                    Failed{{
                      ev.failure_reason ? ` (${ev.failure_reason})` : ''
                    }}
                  </span>
                </td>
                <td class="py-2 pr-4 font-mono text-gray-500 text-xs">
                  {{ ev.client_ip || '—' }}
                </td>
                <td class="py-2 text-gray-600 text-xs">{{ ev.role || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div
          class="flex items-center justify-between mt-4 text-sm text-gray-600"
        >
          <span>Showing {{ events.length }} of {{ eventTotal }} events</span>
          <div class="flex gap-2">
            <button
              @click="prevPage"
              :disabled="currentPage === 0"
              class="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              @click="nextPage"
              :disabled="(currentPage + 1) * pageSize >= eventTotal"
              class="px-3 py-1 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

export default {
  name: 'AdminUsers',
  setup() {
    const authStore = useAuthStore();
    const loading = ref(false);
    const error = ref(null);
    const activeTab = ref('users');

    const users = ref([]);
    const userTotal = ref(0);

    const events = ref([]);
    const eventTotal = ref(0);
    const currentPage = ref(0);
    const pageSize = 100;
    const filterUsername = ref('');
    const filterSuccess = ref('');

    let debounceTimer = null;

    const fetchUsers = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/users`,
          { method: 'GET' }
        );
        users.value = data.users || [];
        userTotal.value = data.total || 0;
      } catch (err) {
        error.value = err.message || 'Failed to fetch users';
      } finally {
        loading.value = false;
      }
    };

    const fetchLoginEvents = async () => {
      loading.value = true;
      error.value = null;
      try {
        const params = new URLSearchParams({
          limit: pageSize,
          offset: currentPage.value * pageSize,
        });
        if (filterUsername.value) params.set('username', filterUsername.value);
        if (filterSuccess.value !== '')
          params.set('success', filterSuccess.value);

        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/users/login-events?${params}`,
          { method: 'GET' }
        );
        events.value = data.events || [];
        eventTotal.value = data.total || 0;
      } catch (err) {
        error.value = err.message || 'Failed to fetch login events';
      } finally {
        loading.value = false;
      }
    };

    const debouncedFetch = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentPage.value = 0;
        fetchLoginEvents();
      }, 400);
    };

    const prevPage = () => {
      if (currentPage.value > 0) {
        currentPage.value--;
        fetchLoginEvents();
      }
    };

    const nextPage = () => {
      currentPage.value++;
      fetchLoginEvents();
    };

    const formatDate = iso => {
      if (!iso) return '—';
      return new Date(iso).toLocaleString();
    };

    const roleBadgeClass = role => {
      const map = {
        admin:
          'bg-purple-100 text-purple-800 px-2 py-0.5 rounded text-xs font-medium',
        club_manager:
          'bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs font-medium',
        team_manager:
          'bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs font-medium',
        'team-manager':
          'bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded text-xs font-medium',
        team_player:
          'bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs font-medium',
        'team-player':
          'bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs font-medium',
      };
      return (
        map[role] ||
        'bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs font-medium'
      );
    };

    onMounted(fetchUsers);

    return {
      loading,
      error,
      activeTab,
      users,
      userTotal,
      events,
      eventTotal,
      currentPage,
      pageSize,
      filterUsername,
      filterSuccess,
      fetchUsers,
      fetchLoginEvents,
      debouncedFetch,
      prevPage,
      nextPage,
      formatDate,
      roleBadgeClass,
    };
  },
};
</script>
