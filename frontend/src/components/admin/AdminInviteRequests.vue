<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold text-gray-900">Invite Requests</h2>
      <div class="flex items-center gap-4">
        <!-- Stats -->
        <div v-if="stats" class="text-sm text-gray-600">
          <span class="font-medium">{{ stats.pending }}</span> pending /
          <span class="font-medium">{{ stats.total }}</span> total
        </div>
        <!-- Filter -->
        <select
          v-model="statusFilter"
          @change="fetchRequests"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Requests</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
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
      <div class="text-gray-400 text-5xl mb-4">📬</div>
      <h3 class="text-lg font-medium text-gray-900 mb-2">No invite requests</h3>
      <p class="text-gray-600">
        {{
          statusFilter
            ? `No ${statusFilter} requests found.`
            : 'No one has requested an invite yet.'
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
              Reason
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Status
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Date
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Actions
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
                {{ request.name }}
              </div>
              <div class="text-sm text-gray-500">{{ request.email }}</div>
            </td>
            <td class="px-4 py-4 text-sm text-gray-500">
              {{ request.team || '-' }}
            </td>
            <td
              class="px-4 py-4 text-sm text-gray-500 max-w-xs truncate"
              :title="request.reason"
            >
              {{ request.reason || '-' }}
            </td>
            <td class="px-4 py-4">
              <span
                :class="{
                  'bg-yellow-100 text-yellow-800': request.status === 'pending',
                  'bg-green-100 text-green-800': request.status === 'approved',
                  'bg-red-100 text-red-800': request.status === 'rejected',
                }"
                class="px-2 py-1 text-xs font-medium rounded-full"
              >
                {{ request.status }}
              </span>
            </td>
            <td class="px-4 py-4 text-sm text-gray-500">
              {{ formatDate(request.created_at) }}
            </td>
            <td class="px-4 py-4 text-sm">
              <div v-if="request.status === 'pending'" class="flex gap-2">
                <button
                  @click="updateStatus(request.id, 'approved')"
                  class="text-green-600 hover:text-green-800 font-medium"
                >
                  Approve
                </button>
                <button
                  @click="updateStatus(request.id, 'rejected')"
                  class="text-red-600 hover:text-red-800 font-medium"
                >
                  Reject
                </button>
              </div>
              <div v-else class="text-gray-400">
                <span v-if="request.reviewed_at" class="text-xs">
                  {{ formatDate(request.reviewed_at) }}
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination placeholder -->
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

// State
const requests = ref([]);
const stats = ref(null);
const loading = ref(false);
const error = ref(null);
const statusFilter = ref('');

// Fetch invite requests
const fetchRequests = async () => {
  loading.value = true;
  error.value = null;

  try {
    const headers = authStore.getAuthHeaders();
    let url = `${getApiBaseUrl()}/api/invite-requests`;
    if (statusFilter.value) {
      url += `?status=${statusFilter.value}`;
    }

    const response = await fetch(url, { headers });

    if (!response.ok) {
      throw new Error('Failed to fetch invite requests');
    }

    requests.value = await response.json();
  } catch (err) {
    console.error('Error fetching invite requests:', err);
    error.value = err.message;
  } finally {
    loading.value = false;
  }
};

// Fetch stats
const fetchStats = async () => {
  try {
    const headers = authStore.getAuthHeaders();
    const response = await fetch(
      `${getApiBaseUrl()}/api/invite-requests/stats`,
      { headers }
    );

    if (response.ok) {
      stats.value = await response.json();
    }
  } catch (err) {
    console.error('Error fetching stats:', err);
  }
};

// Update request status
const updateStatus = async (requestId, newStatus) => {
  const action = newStatus === 'approved' ? 'approve' : 'reject';
  if (!confirm(`Are you sure you want to ${action} this request?`)) return;

  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };

    const response = await fetch(
      `${getApiBaseUrl()}/api/invite-requests/${requestId}/status`,
      {
        method: 'PUT',
        headers,
        body: JSON.stringify({ status: newStatus }),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to ${action} request`);
    }

    // Refresh data
    await Promise.all([fetchRequests(), fetchStats()]);
  } catch (err) {
    console.error(`Error updating request status:`, err);
    alert(`Failed to ${action} request. Please try again.`);
  }
};

// Utility functions
const formatDate = dateString => {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

// Lifecycle
onMounted(async () => {
  await Promise.all([fetchRequests(), fetchStats()]);
});
</script>
