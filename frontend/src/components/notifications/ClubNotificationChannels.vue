<template>
  <div class="club-notifications" data-testid="club-notifications">
    <div class="header">
      <h3 v-if="showTitle" class="title">Live Match Notifications</h3>
      <p class="subtitle">
        When live match events happen, Missing Table posts updates to your
        club's chat channels. A webhook URL or chat ID works like a password —
        anyone holding it can post to your channel — so once saved only its last
        four characters are shown. To change one, Reset and paste it again.
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
      <button class="link" @click="load">Retry</button>
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
            :class="[
              'status',
              enabledFor(platform.id) ? 'configured' : 'paused',
            ]"
            :data-testid="`status-${platform.id}`"
          >
            {{ enabledFor(platform.id) ? '✓ Configured' : 'Paused' }} · ends in
            {{ hintFor(platform.id) }}
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
            :aria-label="`${platform.label} destination`"
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

        <details
          v-if="platform.setup_steps?.length"
          class="setup"
          :open="!configured(platform.id)"
          :data-testid="`setup-${platform.id}`"
        >
          <summary>How to set up {{ platform.label }}</summary>
          <ol>
            <li v-for="(step, i) in platform.setup_steps" :key="i">
              {{ step }}
            </li>
          </ol>
        </details>
        <p v-else class="hint-text">{{ platform.hint }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import { errorMessage } from '@/utils/apiError';

const props = defineProps({
  clubId: {
    type: Number,
    required: true,
  },
  // Off where the page already carries the heading (Admin → Access).
  showTitle: {
    type: Boolean,
    default: true,
  },
});

const authStore = useAuthStore();

// Served by the adapter registry, so a new platform needs no change here.
const platforms = ref([]);

const channels = ref([]); // from GET
const draft = reactive({});
const busy = reactive({});
const validationError = reactive({});
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

const findPlatform = platformId =>
  platforms.value.find(p => p.id === platformId);

const validate = (platform, value) => {
  if (!value) return 'Required';
  if (!new RegExp(platform.destination_pattern).test(value))
    return platform.destination_error;
  return null;
};

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
  const err = validate(findPlatform(platformId), value);
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

const fetchPlatforms = async () => {
  const resp = await fetch(`${getApiBaseUrl()}/api/notifications/platforms`, {
    headers: authHeaders(),
  });
  if (!resp.ok)
    throw new Error(`Failed to load platforms (HTTP ${resp.status})`);
  platforms.value = await resp.json();
};

const fetchChannelRows = async () => {
  const resp = await fetch(urlBase(), { headers: authHeaders() });
  if (!resp.ok)
    throw new Error(`Failed to load channels (HTTP ${resp.status})`);
  channels.value = await resp.json();
};

const fetchChannels = async () => {
  loadError.value = null;
  try {
    await fetchChannelRows();
  } catch (err) {
    loadError.value = err.message;
  }
};

const load = async () => {
  loading.value = true;
  loadError.value = null;
  try {
    await Promise.all([
      platforms.value.length ? null : fetchPlatforms(),
      fetchChannelRows(),
    ]);
  } catch (err) {
    loadError.value = err.message;
  } finally {
    loading.value = false;
  }
};

const save = async platformId => {
  const value = (draft[platformId] || '').trim();
  const platform = findPlatform(platformId);
  const err = validate(platform, value);
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
      throw new Error(errorMessage(body, `Save failed (HTTP ${resp.status})`));
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
  // PATCH flips `enabled` only; the saved destination is kept.
  busy[platformId] = true;
  try {
    const resp = await fetch(`${urlBase()}/${platformId}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: nextEnabled }),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(
        errorMessage(body, `Update failed (HTTP ${resp.status})`)
      );
    }
    showFlash(
      'success',
      nextEnabled
        ? `${findPlatform(platformId).label} channel resumed.`
        : `${findPlatform(platformId).label} channel paused. Its destination is kept.`
    );
  } catch (err) {
    showFlash('error', err.message);
  } finally {
    busy[platformId] = false;
    await fetchChannels();
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
      throw new Error(errorMessage(body, `Test failed (HTTP ${resp.status})`));
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
  () => load()
);

onMounted(load);
</script>

<style scoped>
/* Neutral colours come from the SB-146 theme tokens, so they flip with .dark.
   Tinted ones get an explicit dark pair: write `:global(.dark .x)`, never
   `:global(.dark) .x`, which compiles to a bare `.dark` rule. */
.club-notifications {
  max-width: 720px;
}
.header {
  margin-bottom: 1rem;
}
.title {
  font-size: 1.125rem;
  font-weight: 600;
  color: rgb(var(--color-fg));
}
.subtitle {
  color: rgb(var(--color-fg-muted));
  font-size: 0.875rem;
  margin-top: 0.25rem;
}
.loading {
  padding: 1rem;
  color: rgb(var(--color-fg-muted));
  text-align: center;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.row {
  border: 1px solid rgb(var(--color-line));
  border-radius: 0.5rem;
  padding: 1rem;
  background: rgb(var(--color-card));
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
  color: rgb(var(--color-fg));
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
  color: #047857;
  font-weight: 500;
}
.status.paused {
  color: #b45309;
  font-weight: 500;
}
.status.unconfigured {
  color: rgb(var(--color-fg-muted));
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
  min-width: 0;
  padding: 0.5rem 0.75rem;
  border: 1px solid rgb(var(--color-line));
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
}
.input::placeholder {
  color: rgb(var(--color-fg-muted));
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
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  border-color: rgb(var(--color-line));
}
.btn.secondary:hover:not(:disabled) {
  border-color: rgb(var(--color-fg-muted));
}
.btn.danger {
  background: transparent;
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
  color: rgb(var(--color-fg));
}
.hint-text {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: rgb(var(--color-fg-muted));
}
.setup {
  margin-top: 0.75rem;
  font-size: 0.8125rem;
  color: rgb(var(--color-fg-muted));
}
.setup summary {
  cursor: pointer;
  color: rgb(var(--color-fg));
  font-weight: 500;
}
.setup ol {
  margin: 0.5rem 0 0 1.25rem;
  list-style: decimal;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
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

:global(.dark .club-notifications .status.configured) {
  color: #6ee7b7;
}
:global(.dark .club-notifications .status.paused) {
  color: #fcd34d;
}
:global(.dark .club-notifications .btn.danger) {
  color: #fca5a5;
  border-color: rgb(248 113 113 / 0.4);
}
:global(.dark .club-notifications .btn.danger:hover:not(:disabled)) {
  background: rgb(248 113 113 / 0.12);
}
:global(.dark .club-notifications .field-error) {
  color: #fca5a5;
}
:global(.dark .club-notifications .flash.success) {
  background: rgb(16 185 129 / 0.15);
  color: #6ee7b7;
  border-color: rgb(16 185 129 / 0.35);
}
:global(.dark .club-notifications .flash.error) {
  background: rgb(248 113 113 / 0.12);
  color: #fca5a5;
  border-color: rgb(248 113 113 / 0.35);
}
:global(.dark .club-notifications .flash.warning) {
  background: rgb(245 158 11 / 0.15);
  color: #fcd34d;
  border-color: rgb(245 158 11 / 0.35);
}
:global(.dark .club-notifications .link) {
  color: #93c5fd;
}
</style>
