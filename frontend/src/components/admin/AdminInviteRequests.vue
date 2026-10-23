<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold text-fg">Invite Requests</h2>
      <div class="flex items-center gap-4">
        <!-- Stats -->
        <div v-if="stats" class="text-sm text-fg-muted">
          <span class="font-medium">{{ stats.pending }}</span> pending /
          <span class="font-medium">{{ stats.total }}</span> total
        </div>
        <!-- Filters -->
        <label class="flex items-center gap-2 text-sm text-fg">
          <input
            v-model="iosBetaOnly"
            type="checkbox"
            data-testid="ios-beta-filter"
            class="h-4 w-4 rounded border-line"
            @change="fetchRequests"
          />
          iPhone beta only
        </label>
        <select
          v-model="statusFilter"
          @change="fetchRequests"
          class="px-3 py-2 bg-card border border-line rounded-md text-sm text-fg focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All Requests</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <!-- Preview the email Reject sends (SB-1407) -->
        <button
          type="button"
          data-testid="test-rejection-email"
          class="px-3 py-2 text-sm rounded-md border border-line text-fg hover:bg-surface-alt"
          :disabled="sendingTestEmail"
          @click="sendTestRejectionEmail"
        >
          {{ sendingTestEmail ? 'Sending…' : 'Send test rejection email' }}
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="text-center py-8">
      <div
        class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
      ></div>
      <p class="mt-2 text-fg-muted">Loading requests...</p>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-900 rounded-md p-4"
    >
      <p class="text-red-800 dark:text-red-300">{{ error }}</p>
      <button
        @click="fetchRequests"
        class="mt-2 text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 underline"
      >
        Try again
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="requests.length === 0" class="text-center py-12">
      <div class="text-fg-muted text-5xl mb-4">📬</div>
      <h3 class="text-lg font-medium text-fg mb-2">No invite requests</h3>
      <p class="text-fg-muted">
        {{
          statusFilter || iosBetaOnly
            ? `No ${[statusFilter, iosBetaOnly && 'iPhone beta'].filter(Boolean).join(' ')} requests found.`
            : 'No one has requested an invite yet.'
        }}
      </p>
    </div>

    <!-- Requests Table -->
    <div v-else class="overflow-x-auto">
      <table class="min-w-full divide-y divide-line">
        <thead class="bg-surface-alt">
          <tr>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Requester
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Team
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Reason
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Status
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Date
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-card divide-y divide-line">
          <tr
            v-for="request in requests"
            :key="request.id"
            class="hover:bg-surface-alt"
          >
            <td class="px-4 py-4">
              <div class="text-sm font-medium text-fg">
                {{ request.name }}
              </div>
              <div class="text-sm text-fg-muted">{{ request.email }}</div>
              <span
                v-if="request.wants_ios_beta"
                data-testid="ios-beta-badge"
                class="inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800"
              >
                iPhone beta
              </span>
            </td>
            <td class="px-4 py-4 text-sm text-fg-muted">
              {{ request.team || '-' }}
            </td>
            <td
              class="px-4 py-4 text-sm text-fg-muted max-w-xs truncate"
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
              <div
                v-if="request.invitation"
                data-testid="linked-invite"
                class="mt-1 text-xs text-fg-muted"
              >
                <div class="font-mono">
                  {{ linkedInviteSummary(request.invitation) }}
                </div>
                <div v-if="request.invitation.testflight_status">
                  TestFlight:
                  <span
                    :class="{
                      'text-green-700':
                        request.invitation.testflight_status === 'added',
                      'text-red-700':
                        request.invitation.testflight_status === 'failed',
                    }"
                    :title="request.invitation.testflight_error || ''"
                    >{{ request.invitation.testflight_status }}</span
                  >
                </div>
              </div>
            </td>
            <td class="px-4 py-4 text-sm text-fg-muted">
              {{ formatDate(request.created_at) }}
            </td>
            <td class="px-4 py-4 text-sm">
              <div v-if="request.status === 'pending'" class="flex gap-2">
                <button
                  v-if="!request.invitation_id"
                  data-testid="approve-request"
                  class="text-green-600 hover:text-green-800 font-medium"
                  @click="emit('approve', request)"
                >
                  Approve
                </button>
                <button
                  data-testid="reject-request"
                  class="text-red-600 hover:text-red-800 font-medium"
                  @click="rejectRequest(request)"
                >
                  Reject
                </button>
              </div>
              <div v-else class="flex flex-col gap-1 text-xs">
                <span v-if="request.reviewed_at" class="text-fg-muted">
                  {{ formatDate(request.reviewed_at) }}
                </span>
                <div class="flex gap-3">
                  <button
                    v-if="request.invitation?.status === 'pending'"
                    data-testid="resend-invite"
                    :disabled="resendingIds.has(request.id)"
                    class="text-blue-600 hover:text-blue-800 font-medium disabled:text-fg-muted"
                    @click="resendInviteEmail(request)"
                  >
                    {{
                      resendingIds.has(request.id)
                        ? 'Sending…'
                        : 'Resend invite'
                    }}
                  </button>
                  <!-- A linked request's invitation exists; it can't be undone here. -->
                  <button
                    v-if="!request.invitation_id"
                    data-testid="reset-request"
                    class="text-fg-muted hover:text-fg font-medium"
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
      class="mt-4 text-sm text-fg-muted text-center"
    >
      Showing {{ requests.length }} requests
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import { linkedInviteSummary } from '../../utils/inviteRequests';

// "Approve" hands the request to AdminPanel, which opens the invite form
// pre-filled from it (SB-1312). Sending that invite is what approves the
// request (SB-1392) - there is no approval without an invitation.
const emit = defineEmits(['approve']);

const authStore = useAuthStore();

// State
const requests = ref([]);
const stats = ref(null);
const loading = ref(false);
const error = ref(null);
const statusFilter = ref('');
const iosBetaOnly = ref(false);
// Track per-row "resend in flight" so we can disable the button while the
// POST is pending. Set works fine without a deep reactive wrapper.
const resendingIds = ref(new Set());
const sendingTestEmail = ref(false);

// Send the rejection email to any address, so the template can be checked
// before a real Reject (SB-1407). Touches no invite request.
const sendTestRejectionEmail = async () => {
  const toEmail = window.prompt(
    'Send the rejection email to which address?',
    ''
  );
  if (!toEmail) return;
  const name =
    window.prompt('Name to greet in the email:', 'Test User') || 'Test User';

  sendingTestEmail.value = true;
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/invite-requests/test-rejection-email`,
      {
        method: 'POST',
        headers: {
          ...authStore.getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ to_email: toEmail, name }),
      }
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || response.statusText);
    }
    alert(`Sent — check ${toEmail}.`);
  } catch (err) {
    console.error('Test rejection email failed:', err);
    alert(`Failed to send: ${err.message}`);
  } finally {
    sendingTestEmail.value = false;
  }
};

// Re-send the linked invitation's email (e.g. the requester missed it).
const resendInviteEmail = async request => {
  if (!confirm(`Resend the invite email to ${request.email}?`)) return;
  resendingIds.value.add(request.id);
  // Trigger reactivity by reassigning the Set.
  resendingIds.value = new Set(resendingIds.value);
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/invites/admin/${request.invitation.id}/resend-email`,
      { method: 'POST', headers: authStore.getAuthHeaders() }
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || response.statusText);
    }
    alert(`Resent the invite email to ${request.email}.`);
  } catch (err) {
    console.error('Resend invite email failed:', err);
    alert(`Failed to resend: ${err.message}`);
  } finally {
    resendingIds.value.delete(request.id);
    resendingIds.value = new Set(resendingIds.value);
  }
};

// Set an already-decided request back to pending so the admin can
// approve or reject it again.
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

// Fetch invite requests
const fetchRequests = async () => {
  loading.value = true;
  error.value = null;

  try {
    const headers = authStore.getAuthHeaders();
    const params = new URLSearchParams();
    if (statusFilter.value) params.set('status', statusFilter.value);
    if (iosBetaOnly.value) params.set('ios_beta', 'true');
    const query = params.toString();
    const url = `${getApiBaseUrl()}/api/invite-requests${query ? `?${query}` : ''}`;

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

// Reject a request; the backend emails the requester (SB-1392).
const rejectRequest = async request => {
  if (!confirm(`Reject this request? ${request.email} will be emailed.`))
    return;

  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };

    const response = await fetch(
      `${getApiBaseUrl()}/api/invite-requests/${request.id}/status`,
      {
        method: 'PUT',
        headers,
        body: JSON.stringify({ status: 'rejected' }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to reject request');
    }

    // Refresh data
    await Promise.all([fetchRequests(), fetchStats()]);
  } catch (err) {
    console.error(`Error rejecting request:`, err);
    alert('Failed to reject request. Please try again.');
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
