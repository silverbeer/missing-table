<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold text-gray-900">Channel Access Requests</h2>
      <div class="flex items-center gap-4">
        <!-- Stats -->
        <div v-if="stats" class="text-sm text-gray-600">
          <span class="font-medium">{{ stats.pending_total }}</span> pending
          <span class="text-gray-400"
            >({{ stats.pending_telegram }} Telegram /
            {{ stats.pending_discord }} Discord)</span
          >
          &nbsp;/&nbsp;
          <span class="font-medium">{{ stats.total }}</span> total
        </div>
        <!-- Platform filter -->
        <select
          v-model="platformFilter"
          @change="fetchRequests"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Platforms</option>
          <option value="telegram">Telegram</option>
          <option value="discord">Discord</option>
        </select>
        <!-- Status filter -->
        <select
          v-model="statusFilter"
          @change="fetchRequests"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="denied">Denied</option>
        </select>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="text-center py-8">
      <div
        class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
      ></div>
      <p class="mt-2 text-gray-600">Loading requests...</p>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4"
    >
      <p class="text-red-800">{{ error }}</p>
      <button
        @click="fetchRequests"
        class="mt-2 text-sm text-red-600 hover:text-red-800 underline"
      >
        Try again
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="requests.length === 0" class="text-center py-12">
      <div class="text-gray-400 text-5xl mb-4">📡</div>
      <h3 class="text-lg font-medium text-gray-900 mb-2">
        No channel access requests
      </h3>
      <p class="text-gray-600">
        {{
          statusFilter || platformFilter
            ? 'No requests match the current filters.'
            : 'No one has requested channel access yet.'
        }}
      </p>
    </div>

    <!-- Requests Table -->
    <div v-else class="overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Requester
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Team
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Telegram
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Discord
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Requested
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr
            v-for="request in requests"
            :key="request.id"
            class="hover:bg-gray-50"
          >
            <td class="px-4 py-4">
              <div class="text-sm font-medium text-gray-900">
                {{ request.user_display_name || '—' }}
              </div>
              <div class="text-sm text-gray-500">
                {{ request.user_email || '—' }}
              </div>
            </td>
            <td class="px-4 py-4 text-sm text-gray-500">
              {{ request.team_name || '—' }}
            </td>

            <!-- Telegram column -->
            <td class="px-4 py-4">
              <div v-if="request.telegram_status !== 'none'">
                <div class="text-sm text-gray-700 mb-1">
                  @{{ request.telegram_handle || '—' }}
                </div>
                <span
                  :class="statusBadgeClass(request.telegram_status)"
                  class="px-2 py-1 text-xs font-medium rounded-full"
                >
                  {{ request.telegram_status }}
                </span>
                <div
                  v-if="request.telegram_status === 'pending'"
                  class="flex gap-2 mt-2"
                >
                  <button
                    @click="updateStatus(request.id, 'telegram', 'approved')"
                    class="text-green-600 hover:text-green-800 text-xs font-medium"
                  >
                    Approve
                  </button>
                  <button
                    @click="updateStatus(request.id, 'telegram', 'denied')"
                    class="text-red-600 hover:text-red-800 text-xs font-medium"
                  >
                    Deny
                  </button>
                </div>
                <div
                  v-else-if="request.telegram_reviewed_at"
                  class="text-xs text-gray-400 mt-1"
                >
                  {{ formatDate(request.telegram_reviewed_at) }}
                </div>
              </div>
              <span v-else class="text-xs text-gray-400">Not requested</span>
            </td>

            <!-- Discord column -->
            <td class="px-4 py-4">
              <div v-if="request.discord_status !== 'none'">
                <div class="text-sm text-gray-700 mb-1">
                  {{ request.discord_handle || '—' }}
                </div>
                <span
                  :class="statusBadgeClass(request.discord_status)"
                  class="px-2 py-1 text-xs font-medium rounded-full"
                >
                  {{ request.discord_status }}
                </span>
                <div
                  v-if="request.discord_status === 'pending'"
                  class="flex gap-2 mt-2"
                >
                  <button
                    @click="updateStatus(request.id, 'discord', 'approved')"
                    class="text-green-600 hover:text-green-800 text-xs font-medium"
                  >
                    Approve
                  </button>
                  <button
                    @click="updateStatus(request.id, 'discord', 'denied')"
                    class="text-red-600 hover:text-red-800 text-xs font-medium"
                  >
                    Deny
                  </button>
                </div>
                <div
                  v-else-if="request.discord_reviewed_at"
                  class="text-xs text-gray-400 mt-1"
                >
                  {{ formatDate(request.discord_reviewed_at) }}
                </div>
              </div>
              <span v-else class="text-xs text-gray-400">Not requested</span>
            </td>

            <td class="px-4 py-4 text-sm text-gray-500">
              {{ formatDate(request.created_at) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Count -->
    <div
      v-if="requests.length > 0"
      class="mt-4 text-sm text-gray-500 text-center"
    >
      Showing {{ requests.length }} requests
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

const authStore = useAuthStore();

const requests = ref([]);
const stats = ref(null);
const loading = ref(false);
const error = ref(null);
const statusFilter = ref('');
const platformFilter = ref('');

const fetchRequests = async () => {
  loading.value = true;
  error.value = null;

  try {
    const headers = authStore.getAuthHeaders();
    const params = new URLSearchParams();
    if (statusFilter.value) params.set('status', statusFilter.value);
    if (platformFilter.value) params.set('platform', platformFilter.value);

    const url = `${getApiBaseUrl()}/api/channel-requests${params.toString() ? '?' + params.toString() : ''}`;
    const response = await fetch(url, { headers });

    if (!response.ok) throw new Error('Failed to fetch channel requests');
    requests.value = await response.json();
  } catch (err) {
    console.error('Error fetching channel requests:', err);
    error.value = err.message;
  } finally {
    loading.value = false;
  }
};

const fetchStats = async () => {
  try {
    const headers = authStore.getAuthHeaders();
    const response = await fetch(
      `${getApiBaseUrl()}/api/channel-requests/stats`,
      { headers }
    );
    if (response.ok) {
      stats.value = await response.json();
    }
  } catch (err) {
    console.error('Error fetching channel request stats:', err);
  }
};

const updateStatus = async (requestId, platform, newStatus) => {
  const action = newStatus === 'approved' ? 'approve' : 'deny';
  if (!confirm(`Are you sure you want to ${action} this ${platform} request?`))
    return;

  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };

    const response = await fetch(
      `${getApiBaseUrl()}/api/channel-requests/${requestId}/status`,
      {
        method: 'PUT',
        headers,
        body: JSON.stringify({ platform, status: newStatus }),
      }
    );

    if (!response.ok) throw new Error(`Failed to ${action} request`);

    await Promise.all([fetchRequests(), fetchStats()]);
  } catch (err) {
    console.error('Error updating channel request status:', err);
    alert(`Failed to ${action} request. Please try again.`);
  }
};

const statusBadgeClass = status => ({
  'bg-yellow-100 text-yellow-800': status === 'pending',
  'bg-green-100 text-green-800': status === 'approved',
  'bg-red-100 text-red-800': status === 'denied',
  'bg-gray-100 text-gray-600': status === 'none',
});

const formatDate = dateString => {
  if (!dateString) return '—';
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

onMounted(async () => {
  await Promise.all([fetchRequests(), fetchStats()]);
});
</script>
