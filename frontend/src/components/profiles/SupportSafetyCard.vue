<template>
  <section class="safety-card" data-testid="support-safety-card">
    <header class="safety-header">
      <h3>Support &amp; Safety</h3>
    </header>

    <ul class="safety-links">
      <li>
        <SupportEmailLink display-text="Contact Support" />
      </li>
    </ul>

    <div class="blocked-section">
      <h4 class="blocked-title">Blocked Users</h4>

      <p v-if="loading && !loaded" class="blocked-help">Loading…</p>
      <p
        v-else-if="loadFailed"
        class="blocked-help is-error"
        data-testid="blocked-load-error"
      >
        Couldn't load your blocked users.
        <button type="button" class="link-button" @click="load">Retry</button>
      </p>
      <p
        v-else-if="blocks.length === 0"
        class="blocked-help"
        data-testid="blocked-empty"
      >
        People you block or report in live chat show up here.
      </p>
      <ul v-else class="blocked-list" data-testid="blocked-list">
        <li v-for="user in blocks" :key="user.user_id" class="blocked-row">
          <span class="blocked-name">{{
            user.username || 'Unknown user'
          }}</span>
          <button
            type="button"
            class="unblock-button"
            :data-testid="`unblock-${user.user_id}`"
            :disabled="unblocking === user.user_id"
            @click="unblock(user)"
          >
            Unblock
          </button>
        </li>
      </ul>

      <p
        v-if="actionError"
        class="blocked-help is-error"
        role="status"
        data-testid="unblock-error"
      >
        {{ actionError }}
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import SupportEmailLink from '@/components/SupportEmailLink.vue';
import { useBlockedUsers } from '@/composables/useBlockedUsers';

// Profile → Support & Safety (SB-1324): the web counterpart of the iOS
// Profile section — support, and the people you've blocked in chat. The
// privacy policy is linked from the site footer (SB-1326).
const {
  blocks,
  loaded,
  loading,
  error,
  load,
  unblock: unblockUser,
} = useBlockedUsers();

const loadFailed = computed(() => !loaded.value && !!error.value);
const unblocking = ref(null);
const actionError = ref('');

async function unblock(user) {
  unblocking.value = user.user_id;
  actionError.value = '';
  try {
    await unblockUser(user.user_id);
  } catch (e) {
    actionError.value = e.message || 'Could not unblock this user';
  } finally {
    unblocking.value = null;
  }
}

onMounted(load);
</script>

<style scoped>
.safety-card {
  background: rgb(var(--color-card));
  border: 1px solid rgb(var(--color-line));
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
}

.safety-header h3 {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 700;
  color: rgb(var(--color-fg));
}

.safety-links {
  list-style: none;
  margin: 0 0 16px;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}

.blocked-title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--color-fg));
}

.blocked-help {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
  line-height: 1.4;
}

.blocked-help.is-error {
  color: #b91c1c;
  margin-top: 8px;
}

.blocked-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.blocked-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 44px;
  border-bottom: 1px solid rgb(var(--color-line));
}

.blocked-row:last-child {
  border-bottom: none;
}

.blocked-name {
  color: rgb(var(--color-fg));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.unblock-button,
.link-button {
  background: none;
  border: none;
  padding: 8px 0;
  color: #2563eb;
  font-weight: 600;
  cursor: pointer;
}

.unblock-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
