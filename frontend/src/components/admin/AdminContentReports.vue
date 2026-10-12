<template>
  <div>
    <div class="flex flex-wrap justify-between items-center gap-3 mb-6">
      <div>
        <h2 class="text-xl font-bold text-fg">Content Reports</h2>
        <p class="text-sm text-fg-muted">
          Live chat messages users reported. Reporting also blocked the author
          for the reporter.
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-fg-muted" data-testid="pending-count">
          <span class="font-medium">{{ pendingCount }}</span> pending
        </span>
        <select
          v-model="statusFilter"
          data-testid="report-status-filter"
          class="px-3 py-2 bg-card text-fg border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          @change="fetchReports"
        >
          <option value="">All (pending first)</option>
          <option value="pending">Pending</option>
          <option value="actioned">Actioned</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="text-center py-8">
      <div
        class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
      ></div>
      <p class="mt-2 text-fg-muted">Loading reports...</p>
    </div>

    <div
      v-else-if="error"
      class="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-md p-4"
      data-testid="reports-error"
    >
      <p class="text-red-800 dark:text-red-300">{{ error }}</p>
      <button
        class="mt-2 text-sm text-red-600 hover:text-red-800 underline"
        @click="fetchReports"
      >
        Try again
      </button>
    </div>

    <div
      v-else-if="reports.length === 0"
      class="text-center py-12"
      data-testid="reports-empty"
    >
      <h3 class="text-lg font-medium text-fg mb-2">No content reports</h3>
      <p class="text-fg-muted">
        {{
          statusFilter
            ? 'No reports match this filter.'
            : 'Nobody has reported a chat message.'
        }}
      </p>
    </div>

    <ul v-else class="space-y-3" data-testid="reports-list">
      <li
        v-for="report in reports"
        :key="report.id"
        class="bg-card border border-line rounded-lg p-4"
        :data-testid="`report-${report.id}`"
      >
        <div class="flex flex-wrap items-center gap-2 mb-2 text-sm">
          <span
            class="px-2 py-0.5 text-xs font-medium rounded-full"
            :class="statusBadgeClass(report.status)"
          >
            {{ report.status }}
          </span>
          <span class="font-medium text-fg">
            {{ REPORT_REASON_LABELS[report.reason] || report.reason }}
          </span>
          <span class="text-fg-muted">·</span>
          <span class="text-fg-muted">
            {{ report.reported_username || 'Deleted account' }}
          </span>
          <span class="text-fg-muted">·</span>
          <span class="text-fg-muted">match {{ report.match_id }}</span>
          <span class="text-fg-muted ml-auto">
            {{ formatDate(report.created_at) }}
          </span>
        </div>

        <blockquote
          class="border-l-4 border-line pl-3 text-fg whitespace-pre-wrap break-words"
        >
          {{ report.message_text }}
        </blockquote>
        <p v-if="report.details" class="mt-2 text-sm text-fg-muted">
          Reporter's note: {{ report.details }}
        </p>

        <div
          v-if="report.status === 'pending'"
          class="flex flex-wrap gap-2 mt-3"
        >
          <button
            type="button"
            class="px-3 py-1.5 text-sm font-medium rounded-md bg-surface-alt text-fg hover:bg-line disabled:opacity-50"
            :disabled="acting === report.id"
            :data-testid="`dismiss-${report.id}`"
            @click="act(report, 'dismiss')"
          >
            Dismiss
          </button>
          <button
            type="button"
            class="px-3 py-1.5 text-sm font-medium rounded-md bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
            :disabled="acting === report.id"
            :data-testid="`delete-message-${report.id}`"
            @click="confirmAction(report, 'delete_message')"
          >
            Delete message
          </button>
          <button
            v-if="report.reported_user_id"
            type="button"
            class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
            :disabled="acting === report.id"
            :data-testid="`ban-user-${report.id}`"
            @click="confirmAction(report, 'ban_user')"
          >
            Delete &amp; ban from chat
          </button>
        </div>
        <p
          v-else-if="report.action"
          class="mt-3 text-xs text-fg-muted"
          data-testid="report-resolution"
        >
          {{ ACTION_LABELS[report.action] || report.action }}
          <template v-if="report.resolved_at">
            · {{ formatDate(report.resolved_at) }}
          </template>
        </p>
      </li>
    </ul>

    <ConfirmModal
      :show="!!pending"
      :title="
        pending?.action === 'ban_user' ? 'Ban from chat?' : 'Delete message?'
      "
      :message="confirmMessage"
      :confirm-text="pending?.action === 'ban_user' ? 'Delete & ban' : 'Delete'"
      :loading="acting !== null"
      variant="danger"
      @confirm="runPending"
      @cancel="pending = null"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import ConfirmModal from '@/components/ConfirmModal.vue';
import {
  REPORT_REASON_LABELS,
  sortReportsPendingFirst,
} from '@/utils/chatSafety';

// Admin review queue for reported chat messages (SB-1324).
// Backend: GET / PATCH /api/admin/content-reports (backend/api/moderation.py).

const ACTION_LABELS = {
  dismiss: 'Dismissed',
  delete_message: 'Message deleted',
  ban_user: 'Message deleted, author banned from chat',
};

const authStore = useAuthStore();

const reports = ref([]);
const loading = ref(false);
const error = ref('');
const statusFilter = ref('');
const acting = ref(null);
// { report, action } awaiting confirmation.
const pending = ref(null);

const pendingCount = computed(
  () => reports.value.filter(r => r.status === 'pending').length
);

const confirmMessage = computed(() => {
  if (!pending.value) return '';
  const who = pending.value.report.reported_username || 'this user';
  return pending.value.action === 'ban_user'
    ? `The message is deleted and ${who} can no longer post in chat. There is no unban yet.`
    : 'The message is removed from the live chat for everyone.';
});

async function fetchReports() {
  loading.value = true;
  error.value = '';
  try {
    const query = statusFilter.value ? `?status=${statusFilter.value}` : '';
    const rows = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/admin/content-reports${query}`
    );
    reports.value = sortReportsPendingFirst(Array.isArray(rows) ? rows : []);
  } catch (e) {
    error.value = e.message || 'Failed to load reports';
  } finally {
    loading.value = false;
  }
}

async function act(report, action) {
  acting.value = report.id;
  error.value = '';
  try {
    const updated = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/admin/content-reports/${report.id}`,
      { method: 'PATCH', body: JSON.stringify({ action }) }
    );
    const next = reports.value.map(r =>
      r.id === report.id ? { ...r, ...(updated || {}) } : r
    );
    reports.value = sortReportsPendingFirst(
      statusFilter.value
        ? next.filter(r => r.status === statusFilter.value)
        : next
    );
  } catch (e) {
    error.value = e.message || 'Failed to update report';
  } finally {
    acting.value = null;
  }
}

function confirmAction(report, action) {
  pending.value = { report, action };
}

async function runPending() {
  const { report, action } = pending.value;
  await act(report, action);
  pending.value = null;
}

function statusBadgeClass(status) {
  if (status === 'pending') {
    return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300';
  }
  if (status === 'actioned') {
    return 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300';
  }
  return 'bg-surface-alt text-fg-muted';
}

function formatDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

onMounted(fetchReports);
</script>
