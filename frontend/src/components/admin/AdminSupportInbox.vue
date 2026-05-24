<template>
  <div data-testid="admin-support-inbox">
    <div class="flex items-start justify-between mb-4 sm:mb-6">
      <h2 class="text-xl sm:text-2xl font-bold">Support Inbox</h2>
      <span
        v-if="unreadCount > 0"
        class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800"
        :aria-label="`${unreadCount} unread message${unreadCount === 1 ? '' : 's'}`"
        data-testid="support-inbox-unread-badge"
      >
        {{ unreadCount }} unread
      </span>
    </div>

    <div
      v-if="error"
      class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4"
      role="alert"
    >
      {{ error }}
    </div>

    <SupportThreadView
      v-if="activeThread"
      :thread="activeThread"
      :sending="sending"
      @back="closeThread"
      @reply="onReply"
      @set-status="onSetStatus"
      @mark-all-read="onMarkAllRead"
    />
    <SupportInboxList
      v-else
      :threads="threads"
      :loading="loading"
      :current-status="currentStatus"
      @select="openThread"
      @filter="onFilter"
      @load-more="onLoadMore"
      @search="onSearch"
    />
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue';
import { useSupportInbox } from '@/composables/useSupportInbox';
import SupportInboxList from './SupportInboxList.vue';
import SupportThreadView from './SupportThreadView.vue';

const {
  threads,
  activeThread,
  unreadCount,
  loading,
  sending,
  error,
  currentStatus,
  loadThreads,
  openThread,
  closeThread,
  sendReply,
  setStatus,
  markAllRead,
  startPolling,
  stopPolling,
} = useSupportInbox();

const onFilter = status => {
  loadThreads({ status });
};

const onLoadMore = () => {
  if (threads.value.nextCursor) {
    loadThreads({ cursor: threads.value.nextCursor });
  }
};

const onSearch = mtN => {
  openThread(mtN);
};

const onReply = async body => {
  try {
    await sendReply(body);
  } catch (_e) {
    // Error already set on composable; nothing to do here.
  }
};

const onSetStatus = status => {
  setStatus(status);
};

const onMarkAllRead = () => {
  markAllRead();
};

onMounted(() => {
  loadThreads();
  startPolling();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>
