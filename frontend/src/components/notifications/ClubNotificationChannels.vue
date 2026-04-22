<template>
  <div class="club-notifications" data-testid="club-notifications">
    <div class="header">
      <h3 class="title">Live Match Notifications</h3>
      <p class="subtitle">
        When live match events happen, Missing Table can post updates to your
        club's Telegram group and/or Discord channel. Configure each platform
        below. Destinations are write-only: once saved, you can test or reset
        them, but the full value is never displayed again.
      </p>
    </div>

    <!-- Inline flash message -->
    <div
      v-if="flash"
      :class="['flash', flash.kind]"
      :data-testid="`flash-${flash.kind}`"
    >
      {{ flash.text }}
    </div>

    <div v-if="loading" class="loading" data-testid="loading">
      Loading channels…
    </div>

    <div v-else-if="loadError" class="flash error">
      {{ loadError }}
      <button class="link" @click="fetchChannels">Retry</button>
    </div>

    <div v-else class="rows">
      <div
        v-for="platform in platforms"
        :key="platform.id"
        class="row"
        :data-testid="`row-${platform.id}`"
      >
        <div class="row-header">
          <span class="platform-name">
            <span class="icon" aria-hidden="true">{{ platform.icon }}</span>
            {{ platform.label }}
          </span>
          <span
            v-if="configured(platform.id)"
            class="status configured"
            :data-testid="`status-${platform.id}`"
          >
            ✓ Configured (ends …{{ hintFor(platform.id) }})
          </span>
          <span v-else class="status unconfigured">Not configured</span>
        </div>

        <!-- Configured: show toggle + test + reset -->
        <div v-if="configured(platform.id)" class="row-actions">
          <label class="toggle">
            <input
              type="checkbox"
              :checked="enabledFor(platform.id)"
              :disabled="busy[platform.id]"
              :data-testid="`toggle-${platform.id}`"
              @change="toggleEnabled(platform.id, $event.target.checked)"
            />
            <span>Enabled</span>
          </label>

          <button
            class="btn secondary"
            :disabled="busy[platform.id] || !enabledFor(platform.id)"
            :data-testid="`test-${platform.id}`"
            @click="testSend(platform.id)"
          >
            Send test
          </button>

          <button
            class="btn danger"
            :disabled="busy[platform.id]"
            :data-testid="`reset-${platform.id}`"
            @click="reset(platform.id)"
          >
            Reset
          </button>
        </div>

        <!-- Not configured: input + save -->
        <div v-else class="row-input">
          <input
            v-model="draft[platform.id]"
            :placeholder="platform.placeholder"
            :data-testid="`input-${platform.id}`"
            class="input"
            :disabled="busy[platform.id]"
            @input="clearValidationError(platform.id)"
          />
          <button
            class="btn primary"
            :disabled="!canSave(platform.id) || busy[platform.id]"
            :data-testid="`save-${platform.id}`"
            @click="save(platform.id)"
          >
            {{ busy[platform.id] ? 'Saving…' : 'Save' }}
          </button>
        </div>

        <!-- Per-row validation error -->
        <div
          v-if="validationError[platform.id]"
          class="field-error"
          :data-testid="`error-${platform.id}`"
        >
          {{ validationError[platform.id] }}
        </div>

        <p class="hint-text">{{ platform.hint }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

const props = defineProps({
  clubId: {
    type: Number,
    required: true,
  },
});

const authStore = useAuthStore();

// Mirrors backend validation in backend/api/club_notifications.py
const TELEGRAM_RE = /^(@\w+|-?\d+)$/;
const DISCORD_RE = /^https:\/\/discord(app)?\.com\/api\/webhooks\/\d+\/[\w-]+$/;

const platforms = [
  {
    id: 'telegram',
    label: 'Telegram',
    icon: '✈️',
    placeholder: 'e.g. -1001234567890 or @channelname',
    hint: 'Paste the chat_id for a group the Missing Table bot has been added to, or an @channel username.',
    validator: v => {
      if (!v) return 'Required';
      if (!TELEGRAM_RE.test(v))
        return 'Must be a numeric chat_id (e.g. -1001234567890) or @channelname';
      return null;
    },
  },
  {
    id: 'discord',
    label: 'Discord',
    icon: '💬',
    placeholder: 'https://discord.com/api/webhooks/…/…',
    hint: 'Create a webhook on your Discord channel (Channel Settings → Integrations → Webhooks) and paste the full URL.',
    validator: v => {
      if (!v) return 'Required';
      if (!DISCORD_RE.test(v))
        return 'Must be a Discord webhook URL (discord.com/api/webhooks/{id}/{token})';
      return null;
    },
  },
];

const channels = ref([]); // from GET
const draft = reactive({ telegram: '', discord: '' });
const busy = reactive({ telegram: false, discord: false });
const validationError = reactive({ telegram: null, discord: null });
const loading = ref(false);
const loadError = ref(null);
const flash = ref(null); // { kind: 'success'|'error'|'warning', text }

let flashTimer = null;
const showFlash = (kind, text, ttlMs = 5000) => {
  flash.value = { kind, text };
  if (flashTimer) clearTimeout(flashTimer);
  flashTimer = setTimeout(() => (flash.value = null), ttlMs);
};

const urlBase = () =>
  `${getApiBaseUrl()}/api/clubs/${props.clubId}/notifications`;
const authHeaders = () => authStore.getAuthHeaders();

const configured = platformId =>
  channels.value.some(c => c.platform === platformId && c.configured);

const hintFor = platformId => {
  const row = channels.value.find(c => c.platform === platformId);
  return row?.hint ?? '';
};

const enabledFor = platformId => {
  const row = channels.value.find(c => c.platform === platformId);
  return !!row?.enabled;
};

const canSave = platformId => {
  const value = (draft[platformId] || '').trim();
  const platform = platforms.find(p => p.id === platformId);
  const err = platform.validator(value);
  if (err && draft[platformId]) {
    // Validation happens only once the user has typed something.
    validationError[platformId] = err;
  } else {
    validationError[platformId] = null;
  }
  return !err;
};

const clearValidationError = platformId => {
  validationError[platformId] = null;
};

const fetchChannels = async () => {
  loading.value = true;
  loadError.value = null;
  try {
    const resp = await fetch(urlBase(), { headers: authHeaders() });
    if (!resp.ok)
      throw new Error(`Failed to load channels (HTTP ${resp.status})`);
    channels.value = await resp.json();
  } catch (err) {
    loadError.value = err.message;
  } finally {
    loading.value = false;
  }
};

const save = async platformId => {
  const value = (draft[platformId] || '').trim();
  const platform = platforms.find(p => p.id === platformId);
  const err = platform.validator(value);
  if (err) {
    validationError[platformId] = err;
    return;
  }

  busy[platformId] = true;
  try {
    const resp = await fetch(`${urlBase()}/${platformId}`, {
      method: 'PUT',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination: value, enabled: true }),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `Save failed (HTTP ${resp.status})`);
    }
    draft[platformId] = '';
    showFlash('success', `${platform.label} channel saved.`);
    await fetchChannels();
  } catch (err) {
    showFlash('error', err.message);
  } finally {
    busy[platformId] = false;
  }
};

const toggleEnabled = async (platformId, nextEnabled) => {
  // Enabling/disabling requires the destination again. We don't have it, so
  // we PUT with a placeholder — but the API requires the real value. Instead,
  // we explicitly disable by calling DELETE, and require the user to re-save
  // to re-enable. Simpler contract; no storing destinations in the client.
  if (nextEnabled) {
    // Revert the toggle visually by refreshing state.
    await fetchChannels();
    showFlash(
      'warning',
      'Re-saving required. Use Reset, then Save with the destination again to re-enable.'
    );
    return;
  }
  busy[platformId] = true;
  try {
    const resp = await fetch(`${urlBase()}/${platformId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!resp.ok) throw new Error(`Disable failed (HTTP ${resp.status})`);
    showFlash('success', 'Channel disabled.');
    await fetchChannels();
  } catch (err) {
    showFlash('error', err.message);
    await fetchChannels();
  } finally {
    busy[platformId] = false;
  }
};

const reset = async platformId => {
  if (
    !confirm(
      `Remove the ${platformId} notification channel for this club? The destination will have to be re-entered.`
    )
  )
    return;
  busy[platformId] = true;
  try {
    const resp = await fetch(`${urlBase()}/${platformId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!resp.ok) throw new Error(`Reset failed (HTTP ${resp.status})`);
    showFlash('success', 'Channel cleared.');
    await fetchChannels();
  } catch (err) {
    showFlash('error', err.message);
  } finally {
    busy[platformId] = false;
  }
};

const testSend = async platformId => {
  busy[platformId] = true;
  try {
    const resp = await fetch(`${urlBase()}/${platformId}/test`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (resp.status === 429) {
      showFlash('warning', 'Rate limit: max 5 test sends per minute per club.');
      return;
    }
    if (resp.status === 503) {
      showFlash(
        'warning',
        'Notifications are globally disabled by an administrator.'
      );
      return;
    }
    if (resp.status === 501) {
      showFlash(
        'warning',
        'Live send is not wired up yet — the notification dispatcher ships in a later phase.'
      );
      return;
    }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `Test failed (HTTP ${resp.status})`);
    }
    const body = await resp.json();
    if (body.success) {
      showFlash('success', `Test message sent to ${platformId}.`);
    } else {
      showFlash('error', `Send failed: ${body.error || 'unknown error'}`);
    }
  } catch (err) {
    showFlash('error', err.message);
  } finally {
    busy[platformId] = false;
  }
};

watch(
  () => props.clubId,
  () => fetchChannels()
);

onMounted(fetchChannels);
</script>

<style scoped>
.club-notifications {
  max-width: 720px;
}
.header {
  margin-bottom: 1rem;
}
.title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
}
.subtitle {
  color: #6b7280;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}
.loading {
  padding: 1rem;
  color: #6b7280;
  text-align: center;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.row {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  background: #fff;
}
.row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.platform-name {
  font-weight: 500;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
.icon {
  font-size: 1rem;
}
.status {
  font-size: 0.8125rem;
}
.status.configured {
  color: #059669;
  font-weight: 500;
}
.status.unconfigured {
  color: #9ca3af;
}
.row-actions {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}
.row-input {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
}
.input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.875rem;
}
.input:focus {
  outline: 2px solid #3b82f6;
  outline-offset: -1px;
  border-color: #3b82f6;
}
.btn {
  padding: 0.5rem 0.875rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.primary {
  background: #2563eb;
  color: #fff;
}
.btn.primary:hover:not(:disabled) {
  background: #1d4ed8;
}
.btn.secondary {
  background: #f3f4f6;
  color: #111827;
  border-color: #d1d5db;
}
.btn.secondary:hover:not(:disabled) {
  background: #e5e7eb;
}
.btn.danger {
  background: #fff;
  color: #b91c1c;
  border-color: #fecaca;
}
.btn.danger:hover:not(:disabled) {
  background: #fee2e2;
}
.toggle {
  display: inline-flex;
  gap: 0.375rem;
  align-items: center;
  font-size: 0.875rem;
  color: #374151;
}
.hint-text {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #6b7280;
}
.field-error {
  color: #b91c1c;
  font-size: 0.8125rem;
  margin-top: 0.375rem;
}
.flash {
  padding: 0.625rem 0.875rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  margin-bottom: 1rem;
  border: 1px solid transparent;
}
.flash.success {
  background: #ecfdf5;
  color: #065f46;
  border-color: #a7f3d0;
}
.flash.error {
  background: #fef2f2;
  color: #991b1b;
  border-color: #fecaca;
}
.flash.warning {
  background: #fffbeb;
  color: #92400e;
  border-color: #fde68a;
}
.link {
  margin-left: 0.5rem;
  color: #2563eb;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  text-decoration: underline;
  padding: 0;
}
</style>
