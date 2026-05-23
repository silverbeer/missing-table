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
        <!-- Test email -->
        <button
          type="button"
          class="px-3 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
          :disabled="sendingTestEmail"
          @click="sendTestApprovalEmail"
        >
          {{ sendingTestEmail ? 'Sending…' : 'Send test approval email' }}
        </button>
        <!-- Filter -->
        <select
          v-model="statusFilter"
          @change="fetchRequests"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
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
        class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
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
              <div v-else class="flex flex-col gap-1 text-xs">
                <span v-if="request.reviewed_at" class="text-gray-400">
                  {{ formatDate(request.reviewed_at) }}
                </span>
                <div class="flex gap-3">
                  <button
                    v-if="request.status === 'approved'"
                    :disabled="resendingIds.has(request.id)"
                    class="text-blue-600 hover:text-blue-800 font-medium disabled:text-gray-400"
                    @click="resendApprovalEmail(request)"
                  >
                    {{
                      resendingIds.has(request.id) ? 'Sending…' : 'Resend email'
                    }}
                  </button>
                  <button
                    class="text-gray-600 hover:text-gray-800 font-medium"
                    @click="resetToPending(request.id)"
                  >
                    Reset
                  </button>
                </div>
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
const sendingTestEmail = ref(false);
// Track per-row "resend in flight" so we can disable the button while the
// POST is pending. Set works fine without a deep reactive wrapper.
const resendingIds = ref(new Set());

// Re-fire the approval email for an already-approved request (e.g. user
// missed the original, or admin wants to redo the test). Reuses the
// admin test-email endpoint so we don't duplicate sending logic.
const resendApprovalEmail = async request => {
  if (!confirm(`Resend approval email to ${request.email}?`)) return;
  resendingIds.value.add(request.id);
  // Trigger reactivity by reassigning the Set.
  resendingIds.value = new Set(resendingIds.value);
  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };
    const response = await fetch(
      `${getApiBaseUrl()}/api/invite-requests/test-approval-email`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({
          to_email: request.email,
          name: request.name,
        }),
      }
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || response.statusText);
    }
    alert(`Resent approval email to ${request.email}.`);
  } catch (err) {
    console.error('Resend approval email failed:', err);
    alert(`Failed to resend: ${err.message}`);
  } finally {
    resendingIds.value.delete(request.id);
    resendingIds.value = new Set(resendingIds.value);
  }
};

// Set an already-decided request back to pending so the admin can
// re-approve / re-reject. We hit the status endpoint directly (rather
// than going through updateStatus) so the "Are you sure you want to
// approve/reject?" confirm copy in updateStatus doesn't fire.
const resetToPending = async requestId => {
  if (!confirm('Reset this request to pending? Clears the review.')) return;
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
        body: JSON.stringify({ status: 'pending' }),
      }
    );
    if (!response.ok) throw new Error('Failed to reset request');
    await Promise.all([fetchRequests(), fetchStats()]);
  } catch (err) {
    console.error('Reset to pending failed:', err);
    alert('Failed to reset request. Please try again.');
  }
};

// Send a test "your request was approved" email so admins can verify
// the Resend wiring without creating a throwaway invite_request row.
const sendTestApprovalEmail = async () => {
  const toEmail = window.prompt(
    'Send the approval email to which address?',
    ''
  );
  if (!toEmail) return;
  const name =
    window.prompt('Name to greet in the email:', 'Test User') || 'Test User';

  sendingTestEmail.value = true;
  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };
    const response = await fetch(
      `${getApiBaseUrl()}/api/invite-requests/test-approval-email`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ to_email: toEmail, name }),
      }
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || response.statusText);
    }
    alert(`Sent — check ${toEmail}.`);
  } catch (err) {
    console.error('Test approval email failed:', err);
    alert(`Failed to send: ${err.message}`);
  } finally {
    sendingTestEmail.value = false;
  }
};

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
