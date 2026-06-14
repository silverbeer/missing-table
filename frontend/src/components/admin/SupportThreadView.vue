<template>
  <div data-testid="support-thread-view">
    <!-- Header bar -->
    <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
      <button
        type="button"
        class="text-sm text-brand-700 dark:text-brand-300 hover:underline"
        data-testid="thread-back"
        @click="$emit('back')"
      >
        ← Back to inbox
      </button>
      <div class="flex items-center gap-2">
        <button
          v-if="thread.unread_count > 0"
          type="button"
          class="px-3 py-1.5 text-sm bg-surface-alt hover:bg-line rounded-md text-fg-muted"
          data-testid="thread-mark-all-read"
          @click="$emit('mark-all-read')"
        >
          Mark all read
        </button>
        <div class="relative" v-click-outside="closeDropdown">
          <button
            type="button"
            class="px-3 py-1.5 text-sm border border-line rounded-md text-fg-muted hover:bg-surface-alt flex items-center gap-1"
            data-testid="thread-status-dropdown"
            :aria-expanded="dropdownOpen"
            @click="dropdownOpen = !dropdownOpen"
          >
            Set status
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path
                fill-rule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 011.08 1.04l-4.25 4.4a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
          <ul
            v-if="dropdownOpen"
            class="absolute right-0 mt-1 w-48 bg-card border border-line rounded-md shadow-lg z-10 py-1"
            role="menu"
          >
            <li>
              <button
                type="button"
                class="w-full text-left px-3 py-2 text-sm hover:bg-surface-alt"
                data-testid="thread-status-resolved"
                @click="onPickStatus('resolved')"
              >
                Mark resolved
              </button>
            </li>
            <li>
              <button
                type="button"
                class="w-full text-left px-3 py-2 text-sm hover:bg-surface-alt"
                data-testid="thread-status-spam"
                @click="onPickStatus('spam')"
              >
                Mark spam
              </button>
            </li>
            <li>
              <button
                type="button"
                class="w-full text-left px-3 py-2 text-sm hover:bg-surface-alt"
                data-testid="thread-status-reopen"
                @click="onPickStatus('awaiting_admin')"
              >
                Reopen
              </button>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Thread metadata -->
    <div class="mb-4 pb-4 border-b border-line">
      <div class="flex items-center gap-2 mb-2">
        <span
          class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-surface-alt text-fg"
          data-testid="thread-case-number"
        >
          MT-{{ thread.case_number }}
        </span>
        <span
          class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
          :class="statusPillClasses(thread.status)"
          :aria-label="`Status: ${statusLabel(thread.status)}`"
          data-testid="thread-status-pill"
        >
          {{ statusLabel(thread.status) }}
        </span>
      </div>
      <h3 class="text-lg font-semibold text-fg">
        {{ thread.subject || '(no subject)' }}
      </h3>
      <p class="text-sm text-fg-muted">
        {{ thread.participant_name || thread.participant_email }}
        <span v-if="thread.participant_name">
          &lt;{{ thread.participant_email }}&gt;</span
        >
      </p>
    </div>

    <!-- Messages -->
    <ul class="space-y-3 mb-6">
      <li
        v-for="msg in thread.messages || []"
        :key="msg.id"
        :data-testid="`message-${msg.id}`"
        :data-direction="msg.direction"
        class="flex"
        :class="msg.direction === 'outbound' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[80%] rounded-lg px-4 py-3"
          :class="
            msg.direction === 'outbound'
              ? 'bg-brand-50 border border-brand-200'
              : 'bg-surface-alt border border-line'
          "
        >
          <div class="flex items-center gap-2 mb-1 text-xs text-fg-muted">
            <span class="font-medium text-fg-muted">
              {{
                msg.direction === 'outbound'
                  ? msg.from_name || 'Support'
                  : msg.from_name || msg.from_email
              }}
            </span>
            <span>·</span>
            <time :datetime="msg.created_at">{{
              formatTime(msg.created_at)
            }}</time>
          </div>
          <div
            v-if="msg.body_html"
            class="text-sm text-fg prose prose-sm max-w-none"
            data-testid="message-body-html"
            v-html="msg.body_html"
          />
          <div
            v-else
            class="text-sm text-fg whitespace-pre-wrap"
            data-testid="message-body-text"
          >
            {{ msg.body_text }}
          </div>
          <p
            v-if="msg.had_attachments"
            class="mt-2 text-xs italic text-fg-muted"
            data-testid="message-attachments-notice"
          >
            Attachments stripped. Reply via your email client to view them.
          </p>
        </div>
      </li>
    </ul>

    <!-- Reply composer -->
    <form
      class="border-t border-line pt-4"
      data-testid="reply-composer"
      @submit.prevent="onReply"
    >
      <label for="reply-body" class="sr-only">Reply</label>
      <textarea
        id="reply-body"
        v-model="replyBody"
        rows="4"
        placeholder="Write a reply…"
        data-testid="reply-textarea"
        class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 text-sm"
      ></textarea>
      <div class="flex justify-end mt-2">
        <button
          type="submit"
          class="px-4 py-2 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
          data-testid="reply-submit"
          :disabled="sending || !replyBody.trim()"
        >
          <svg
            v-if="sending"
            class="animate-spin h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            />
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
          {{ sending ? 'Sending…' : 'Send reply' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  thread: { type: Object, required: true },
  sending: { type: Boolean, default: false },
});

const emit = defineEmits(['back', 'reply', 'set-status', 'mark-all-read']);

const replyBody = ref('');
const dropdownOpen = ref(false);

const onReply = () => {
  const body = replyBody.value.trim();
  if (!body) return;
  emit('reply', body);
  replyBody.value = '';
};

const onPickStatus = status => {
  dropdownOpen.value = false;
  emit('set-status', status);
};

const closeDropdown = () => {
  dropdownOpen.value = false;
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

const formatTime = iso => {
  if (!iso) return '';
  return new Date(iso).toLocaleString();
};

// Reference props to keep linter happy (we destructure later in tests).
void props;

// Local v-click-outside directive (Vue 3 <script setup> auto-registers
// any `vFoo` const as a directive).
const vClickOutside = {
  mounted(el, binding) {
    el._clickOutsideHandler = event => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event);
      }
    };
    document.addEventListener('click', el._clickOutsideHandler);
  },
  unmounted(el) {
    document.removeEventListener('click', el._clickOutsideHandler);
  },
};
</script>
