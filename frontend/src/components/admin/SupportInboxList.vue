<template>
  <div data-testid="support-inbox-list">
    <!-- Filter bar -->
    <div
      class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4"
    >
      <div
        class="flex flex-wrap gap-2"
        role="tablist"
        aria-label="Status filter"
      >
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          role="tab"
          :aria-selected="currentStatus === tab.value"
          :data-testid="`status-tab-${tab.id}`"
          class="px-3 py-1.5 text-sm rounded-full border transition-colors"
          :class="
            currentStatus === tab.value
              ? 'bg-brand-600 text-white border-brand-600'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          "
          @click="$emit('filter', tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <form class="flex items-center gap-2" @submit.prevent="onSearchSubmit">
        <label class="sr-only" for="support-inbox-mt-search"
          >Jump to case</label
        >
        <input
          id="support-inbox-mt-search"
          v-model="searchInput"
          type="text"
          placeholder="MT-42"
          data-testid="support-inbox-search"
          class="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 w-32"
        />
        <button
          type="submit"
          class="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-md text-gray-700"
          data-testid="support-inbox-search-submit"
        >
          Go
        </button>
      </form>
    </div>

    <!-- Loading / empty / rows -->
    <div
      v-if="loading && threads.items.length === 0"
      class="text-center text-gray-500 py-12"
      data-testid="support-inbox-loading"
    >
      Loading threads…
    </div>

    <div
      v-else-if="threads.items.length === 0"
      class="text-center text-gray-500 py-12 bg-gray-50 rounded-lg"
      data-testid="support-inbox-empty"
    >
      <p class="font-medium mb-1">No threads in this view.</p>
      <p class="text-sm">Try a different status tab.</p>
    </div>

    <ul
      v-else
      class="divide-y divide-gray-200 border border-gray-200 rounded-lg bg-white"
    >
      <li
        v-for="thread in threads.items"
        :key="thread.id"
        :data-testid="`thread-row-${thread.case_number}`"
        class="px-4 py-3 hover:bg-gray-50 cursor-pointer"
        @click="$emit('select', thread.id)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 mb-1">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-gray-100 text-gray-800"
                :data-testid="`thread-case-${thread.case_number}`"
              >
                MT-{{ thread.case_number }}
              </span>
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="statusPillClasses(thread.status)"
                :aria-label="`Status: ${statusLabel(thread.status)}`"
              >
                {{ statusLabel(thread.status) }}
              </span>
              <span
                v-if="thread.unread_count > 0"
                class="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800"
                :data-testid="`thread-unread-${thread.case_number}`"
              >
                {{ thread.unread_count }}
              </span>
            </div>
            <p class="text-sm font-medium text-gray-900 truncate">
              {{ participantDisplay(thread) }}
            </p>
            <p class="text-sm text-gray-700 truncate">
              {{ thread.subject || '(no subject)' }}
            </p>
          </div>
          <div class="text-right text-xs text-gray-500 whitespace-nowrap">
            {{ relativeTime(thread.last_message_at) }}
          </div>
        </div>
      </li>
    </ul>

    <!-- Load more -->
    <div v-if="threads.nextCursor" class="text-center mt-4">
      <button
        type="button"
        class="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-md text-gray-700"
        data-testid="support-inbox-load-more"
        :disabled="loading"
        @click="$emit('load-more')"
      >
        {{ loading ? 'Loading…' : 'Load more' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

defineProps({
  threads: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  currentStatus: { type: String, required: true },
});

const emit = defineEmits(['select', 'filter', 'load-more', 'search']);

const searchInput = ref('');

const tabs = [
  { id: 'attention', label: 'Needs attention', value: 'new,awaiting_admin' },
  { id: 'waiting-user', label: 'Waiting on user', value: 'awaiting_user' },
  { id: 'resolved', label: 'Resolved', value: 'resolved' },
  { id: 'spam', label: 'Spam', value: 'spam' },
  {
    id: 'all',
    label: 'All',
    value: 'new,awaiting_admin,awaiting_user,resolved,spam',
  },
];

const onSearchSubmit = () => {
  const raw = (searchInput.value || '').trim();
  if (!raw) return;
  // Accept "42", "MT-42", "mt-42" — normalize before emitting.
  const match = raw.match(/^(?:MT-)?(\d+)$/i);
  const mtN = match ? `MT-${match[1]}` : raw;
  emit('search', mtN);
};

const statusLabel = s => {
  switch (s) {
    case 'new':
      return 'New';
    case 'awaiting_admin':
      return 'Awaiting admin';
    case 'awaiting_user':
      return 'Awaiting user';
    case 'resolved':
      return 'Resolved';
    case 'spam':
      return 'Spam';
    default:
      return s;
  }
};

const statusPillClasses = s => {
  switch (s) {
    case 'new':
      return 'bg-red-100 text-red-800';
    case 'awaiting_admin':
      return 'bg-orange-100 text-orange-800';
    case 'awaiting_user':
      return 'bg-blue-100 text-blue-800';
    case 'resolved':
      return 'bg-gray-100 text-gray-700';
    case 'spam':
      return 'bg-gray-100 text-gray-500';
    default:
      return 'bg-gray-100 text-gray-700';
  }
};

const participantDisplay = thread => {
  if (thread.participant_name) {
    return `${thread.participant_name} <${thread.participant_email}>`;
  }
  return thread.participant_email;
};

const relativeTime = iso => {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604_800) return `${Math.floor(diffSec / 86_400)}d ago`;
  return new Date(iso).toLocaleDateString();
};
</script>
