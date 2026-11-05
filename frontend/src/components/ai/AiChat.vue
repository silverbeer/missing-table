<template>
  <div class="flex flex-col" data-testid="ai-chat">
    <!-- Header: recent chats and New chat -->
    <div class="flex items-center justify-between gap-2 mb-3">
      <h2 class="text-lg font-semibold text-fg">Ask Missing Table</h2>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="px-3 py-1.5 text-sm border border-line rounded-md text-fg-muted hover:bg-surface-alt"
          data-testid="ai-chat-recent-toggle"
          :aria-expanded="showRecent"
          @click="toggleRecent"
        >
          Recent
        </button>
        <button
          type="button"
          class="px-3 py-1.5 text-sm bg-surface-alt hover:bg-line rounded-md text-fg disabled:opacity-50"
          data-testid="ai-chat-new"
          :disabled="sending"
          @click="newChat"
        >
          New chat
        </button>
      </div>
    </div>

    <!-- Recent conversations -->
    <div
      v-if="showRecent"
      class="mb-3 rounded-lg border border-line bg-card"
      data-testid="ai-chat-recent"
    >
      <p v-if="recentLoading" class="p-3 text-sm text-fg-muted">Loading…</p>
      <p v-else-if="recentError" class="p-3 text-sm text-fg-muted">
        {{ recentError }}
      </p>
      <p v-else-if="recent.length === 0" class="p-3 text-sm text-fg-muted">
        No previous chats yet.
      </p>
      <ul v-else class="divide-y divide-line">
        <li v-for="c in recent" :key="c.id">
          <button
            type="button"
            class="w-full text-left px-3 py-2 text-sm text-fg hover:bg-surface-alt truncate"
            :data-testid="`ai-chat-recent-${c.id}`"
            :disabled="sending"
            @click="openConversation(c.id)"
          >
            {{ c.first_question || 'Untitled chat' }}
          </button>
        </li>
      </ul>
    </div>

    <!-- Messages -->
    <div
      ref="scroller"
      class="overflow-y-auto min-h-64 max-h-[65vh] space-y-3 pb-2"
      data-testid="ai-chat-messages"
      aria-live="polite"
    >
      <!-- Empty state -->
      <div
        v-if="messages.length === 0 && !sending"
        class="py-8 text-center"
        data-testid="ai-chat-empty"
      >
        <p class="text-sm text-fg-muted mb-4">
          Ask about matches, teams, standings and rules.
        </p>
        <div class="flex flex-wrap justify-center gap-2">
          <button
            v-for="q in EXAMPLE_QUESTIONS"
            :key="q"
            type="button"
            class="px-3 py-2 text-sm rounded-full border border-brand-200 bg-brand-50 text-brand-700 hover:bg-brand-100 dark:border-brand-700 dark:bg-brand-900 dark:text-brand-100"
            data-testid="ai-chat-example"
            @click="send(q)"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id"
        class="flex"
        :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        :data-testid="`ai-chat-${msg.role}`"
      >
        <!-- User -->
        <div
          v-if="msg.role === 'user'"
          class="max-w-[85%] rounded-2xl rounded-br-sm px-4 py-2 bg-brand-600 text-white text-sm whitespace-pre-wrap break-words"
        >
          {{ msg.text }}
        </div>

        <!-- Assistant -->
        <div
          v-else
          class="max-w-[95%] sm:max-w-[85%] min-w-0 rounded-2xl rounded-bl-sm px-4 py-2 bg-surface-alt border border-line text-sm text-fg"
        >
          <!-- Limit / error / budget: the text, muted, as a warning -->
          <p
            v-if="msg.warning"
            class="text-amber-800 dark:text-amber-200 italic"
            data-testid="ai-chat-warning"
          >
            {{ msg.warning }}
          </p>
          <!-- Safe: renderMarkdown escapes all HTML before adding its own tags -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div
            v-else-if="msg.html"
            class="ai-answer break-words"
            data-testid="ai-chat-answer"
            v-html="msg.html"
          ></div>

          <div
            v-for="(table, t) in msg.tables"
            :key="t"
            class="mt-3"
            data-testid="ai-chat-table"
          >
            <p v-if="table.title" class="font-semibold mb-1">
              {{ table.title }}
            </p>
            <div class="overflow-x-auto -mx-1">
              <table class="min-w-full text-xs border-collapse">
                <thead>
                  <tr class="border-b border-line">
                    <th
                      v-for="(col, c) in table.columns"
                      :key="c"
                      class="px-1.5 py-1 font-semibold text-fg-muted whitespace-nowrap"
                      :class="
                        table.numeric.includes(c) ? 'text-right' : 'text-left'
                      "
                    >
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, r) in table.rows"
                    :key="r"
                    class="border-b border-line last:border-0"
                    :class="
                      table.highlight.includes(r)
                        ? 'font-bold bg-accent-50 dark:bg-accent-900/40'
                        : ''
                    "
                    :data-highlight="table.highlight.includes(r) || null"
                  >
                    <td
                      v-for="(cell, c) in row"
                      :key="c"
                      class="px-1.5 py-1 whitespace-nowrap"
                      :class="
                        table.numeric.includes(c) ? 'text-right' : 'text-left'
                      "
                    >
                      {{ cell }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <ul
              v-if="table.notes.length"
              class="mt-1 list-disc pl-5 text-xs text-fg-muted"
              data-testid="ai-chat-table-notes"
            >
              <!-- Safe: renderInline escapes all HTML first -->
              <!-- eslint-disable-next-line vue/no-v-html -->
              <li
                v-for="(note, n) in table.notesHtml"
                :key="n"
                v-html="note"
              ></li>
            </ul>
          </div>

          <p
            v-if="msg.escalated"
            class="mt-2 text-xs text-fg-muted"
            data-testid="ai-chat-escalated"
          >
            We've passed this on. Someone from Missing Table may follow up.
          </p>
        </div>
      </div>

      <!-- Thinking -->
      <div
        v-if="sending"
        class="flex justify-start"
        data-testid="ai-chat-thinking"
      >
        <div
          class="rounded-2xl rounded-bl-sm px-4 py-2 bg-surface-alt border border-line text-sm text-fg-muted animate-pulse"
        >
          Thinking…
        </div>
      </div>
    </div>

    <!-- Request error -->
    <p
      v-if="error"
      class="mt-2 rounded-md bg-red-50 dark:bg-red-900/30 px-3 py-2 text-sm text-red-800 dark:text-red-200"
      role="alert"
      data-testid="ai-chat-error"
    >
      {{ error }}
    </p>

    <!-- Composer -->
    <form
      class="mt-3 flex items-end gap-2 border-t border-line pt-3"
      data-testid="ai-chat-form"
      @submit.prevent="send()"
    >
      <label for="ai-chat-input" class="sr-only">Your question</label>
      <textarea
        id="ai-chat-input"
        ref="input"
        v-model="draft"
        rows="2"
        :maxlength="MAX_MESSAGE"
        :disabled="sending"
        placeholder="Ask about a team, match or standings…"
        class="flex-1 resize-none px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 text-base sm:text-sm disabled:opacity-60"
        data-testid="ai-chat-input"
        @keydown.enter="onEnter"
      ></textarea>
      <button
        type="submit"
        class="px-4 py-2 text-sm bg-brand-600 text-white rounded-md hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="ai-chat-send"
        :disabled="sending || !draft.trim()"
      >
        Send
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import {
  renderMarkdown,
  renderInline,
  numericColumns,
  chatErrorMessage,
} from '@/utils/aiChat';

const EXAMPLE_QUESTIONS = [
  'When does my team play next?',
  'Show the U15 Homegrown Northeast standings',
  'How did IFA U14 do last weekend?',
];
const MAX_MESSAGE = 2000;
// An agent turn calls tools and a model; it can outlast the store's 30s
// default, which is sized for plain reads.
const CHAT_TIMEOUT_MS = 90_000;

const authStore = useAuthStore();

const messages = ref([]);
const conversationId = ref(null);
const draft = ref('');
const sending = ref(false);
const error = ref('');
const scroller = ref(null);
const input = ref(null);

const showRecent = ref(false);
const recent = ref([]);
const recentLoading = ref(false);
const recentError = ref('');

let nextId = 0;
const userMessage = text => ({ id: ++nextId, role: 'user', text });

const toTable = table => {
  const notes = Array.isArray(table?.notes) ? table.notes : [];
  return {
    title: table?.title || '',
    columns: Array.isArray(table?.columns) ? table.columns : [],
    rows: Array.isArray(table?.rows) ? table.rows : [],
    highlight: Array.isArray(table?.highlight) ? table.highlight : [],
    numeric: numericColumns(table),
    notes,
    notesHtml: notes.map(renderInline),
  };
};

/** One POST /api/ai/chat reply as a displayable assistant message. */
const assistantMessage = reply => {
  const text = reply.answer ?? reply.message ?? '';
  let warning = '';
  if (reply.status === 'budget_exhausted') {
    warning = reply.message || reply.answer || "You've used up chat for today.";
  } else if (reply.outcome === 'limit' || reply.outcome === 'error') {
    warning = text || "Sorry, I couldn't answer that.";
  }
  return {
    id: ++nextId,
    role: 'assistant',
    warning,
    html: warning ? '' : renderMarkdown(text),
    tables: warning ? [] : (reply.tables || []).map(toTable),
    escalated: reply.outcome === 'escalated',
  };
};

const scrollToBottom = async () => {
  await nextTick();
  const el = scroller.value;
  if (el) el.scrollTop = el.scrollHeight;
};
watch(() => [messages.value.length, sending.value], scrollToBottom);

const send = async preset => {
  const text = (preset ?? draft.value).trim();
  if (!text || sending.value) return;
  if (text.length > MAX_MESSAGE) {
    error.value = `Questions can be up to ${MAX_MESSAGE} characters.`;
    return;
  }

  const typed = draft.value;
  const pending = userMessage(text);
  messages.value.push(pending);
  draft.value = '';
  error.value = '';
  sending.value = true;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
  try {
    const reply = await authStore.apiRequest(`${getApiBaseUrl()}/api/ai/chat`, {
      method: 'POST',
      body: JSON.stringify({
        message: text,
        conversation_id: conversationId.value,
      }),
      signal: controller.signal,
    });
    if (reply?.conversation_id) conversationId.value = reply.conversation_id;
    messages.value.push(assistantMessage(reply || {}));
  } catch (err) {
    // The question didn't land: take it back off the list and give the
    // typed text back so nothing has to be retyped.
    messages.value = messages.value.filter(m => m.id !== pending.id);
    if (preset === undefined) draft.value = typed;
    error.value = chatErrorMessage(err);
  } finally {
    clearTimeout(timer);
    sending.value = false;
    await nextTick();
    input.value?.focus?.();
  }
};

// Enter sends; Shift+Enter (and Enter while an IME is composing) is a newline.
const onEnter = event => {
  if (event.shiftKey || event.isComposing) return;
  event.preventDefault();
  send();
};

const newChat = () => {
  messages.value = [];
  conversationId.value = null;
  error.value = '';
  showRecent.value = false;
};

const loadRecent = async () => {
  recentLoading.value = true;
  recentError.value = '';
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/ai/conversations?limit=10`
    );
    recent.value = Array.isArray(data?.conversations) ? data.conversations : [];
  } catch {
    recentError.value = "Couldn't load your recent chats.";
  } finally {
    recentLoading.value = false;
  }
};

const toggleRecent = () => {
  showRecent.value = !showRecent.value;
  if (showRecent.value) loadRecent();
};

/** Reopen a past conversation. Stored turns carry text only, no tables. */
const openConversation = async id => {
  error.value = '';
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/ai/conversations/${encodeURIComponent(id)}`
    );
    const restored = [];
    for (const turn of data?.turns || []) {
      if (turn.question) restored.push(userMessage(turn.question));
      restored.push(
        turn.answer
          ? assistantMessage({ answer: turn.answer })
          : assistantMessage({
              outcome: 'error',
              answer: 'No answer was recorded for this question.',
            })
      );
    }
    messages.value = restored;
    conversationId.value = data?.id || id;
    showRecent.value = false;
  } catch (err) {
    error.value = chatErrorMessage(err);
  }
};
</script>

<style scoped>
.ai-answer :deep(p + p),
.ai-answer :deep(p + ul),
.ai-answer :deep(p + ol),
.ai-answer :deep(ul + p),
.ai-answer :deep(ol + p) {
  margin-top: 0.5rem;
}
.ai-answer :deep(ul) {
  list-style: disc;
  padding-left: 1.25rem;
}
.ai-answer :deep(ol) {
  list-style: decimal;
  padding-left: 1.25rem;
}
.ai-answer :deep(a) {
  text-decoration: underline;
  font-weight: 500;
}
.ai-answer :deep(code) {
  font-size: 0.85em;
  padding: 0 0.25rem;
  border-radius: 0.25rem;
  background: rgb(var(--color-line) / 0.6);
}
</style>
