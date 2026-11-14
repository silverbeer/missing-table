<template>
  <section class="channel-manager" data-testid="channel-manager">
    <header class="mb-3">
      <h3 v-if="heading" class="text-lg font-semibold text-fg">
        {{ heading }}
      </h3>
      <p class="text-sm text-fg-muted mt-1">
        Missing Table posts live match updates to these chat channels. A webhook
        URL or chat ID works like a password, so once saved only its last four
        characters are shown.
      </p>
      <p class="text-sm text-fg-muted mt-1" data-testid="manager-owns-note">
        These rooms are community-run: you own and moderate them, and Missing
        Table does not. Invite links can be passed on, so treat a room as open
        to anyone who has its link.
      </p>
      <button
        v-if="scopeType !== 'global'"
        class="link-btn mt-1"
        data-testid="open-guide"
        @click="openGuide()"
      >
        Setup guide: Slack, Telegram and Discord
      </button>
    </header>

    <ChannelSetupGuide
      v-if="guide"
      :initial-tab="guide.tab"
      :initial-platform="guide.platform"
      @close="guide = null"
    />

    <div
      v-if="flash"
      :class="['flash', flash.kind]"
      :data-testid="`flash-${flash.kind}`"
      role="status"
    >
      {{ flash.text }}
    </div>

    <p v-if="loading" class="text-sm text-fg-muted" data-testid="loading">
      Loading channels…
    </p>

    <div v-else-if="loadError" class="flash error" data-testid="load-error">
      Channels could not be loaded.
      <button class="link-btn" @click="load">Retry</button>
    </div>

    <template v-else>
      <p
        v-if="!channels.length && formMode !== 'add'"
        class="text-sm text-fg-muted"
        data-testid="no-channels"
      >
        No channels yet. Add one so fans{{
          scopeType === 'global' ? '' : ' or players'
        }}
        get goals, kickoff and full time as they happen.
      </p>

      <ul v-if="channels.length" class="flex flex-col gap-3">
        <li
          v-for="channel in channels"
          :key="channel.id"
          class="channel-row"
          :data-testid="`channel-${channel.id}`"
        >
          <div class="flex items-start justify-between gap-2 flex-wrap">
            <div class="min-w-0">
              <p class="font-medium text-fg break-words">
                {{
                  channel.label || `${platformLabel(channel.platform)} channel`
                }}
              </p>
              <p class="text-xs text-fg-muted">
                {{ platformIcon(channel.platform) }}
                {{ platformLabel(channel.platform) }} ·
                {{ channel.audience === 'players' ? 'Players' : 'Fans' }} · ends
                in {{ channel.hint }}
              </p>
            </div>
            <span
              v-if="!channel.enabled"
              class="pill paused"
              :data-testid="`paused-${channel.id}`"
            >
              Paused
            </span>
            <span
              v-if="channel.post_as_threads"
              class="pill threads"
              :data-testid="`threads-${channel.id}`"
            >
              Match threads
            </span>
          </div>

          <dl class="details">
            <dt>Posts</dt>
            <dd :data-testid="`events-${channel.id}`">
              {{ eventsSummary(channel.event_types) }}
            </dd>
            <dt>Invite link</dt>
            <dd :data-testid="`invite-${channel.id}`">
              <a
                v-if="channel.invite_url"
                :href="channel.invite_url"
                target="_blank"
                rel="noopener noreferrer"
                class="link"
                >{{ channel.invite_url }}</a
              >
              <span v-else class="warn-text">
                None yet. People can't join from Missing Table until you add
                one.
              </span>
            </dd>
            <dt>Last post</dt>
            <dd
              :data-testid="`delivery-${channel.id}`"
              :class="{
                'warn-text': channel.last_delivery?.status === 'failed',
              }"
            >
              {{ deliverySummary(channel) }}
            </dd>
          </dl>

          <div
            v-if="formMode !== channel.id"
            class="flex items-center gap-2 flex-wrap mt-3"
          >
            <label class="inline-flex items-center gap-1.5 text-sm text-fg">
              <input
                type="checkbox"
                :checked="channel.enabled"
                :disabled="busyId === channel.id"
                :data-testid="`toggle-${channel.id}`"
                @change="setEnabled(channel, $event.target.checked)"
              />
              Enabled
            </label>
            <button
              class="btn secondary"
              :disabled="busyId === channel.id || !channel.enabled"
              :data-testid="`test-${channel.id}`"
              @click="sendTest(channel)"
            >
              Send test
            </button>
            <button
              class="btn secondary"
              :disabled="busyId === channel.id"
              :data-testid="`edit-${channel.id}`"
              @click="openEdit(channel)"
            >
              Edit
            </button>
            <button
              class="btn danger"
              :disabled="busyId === channel.id"
              :data-testid="`remove-${channel.id}`"
              @click="remove(channel)"
            >
              Remove
            </button>
          </div>

          <ChannelForm
            v-else
            v-model="form"
            :platforms="platforms"
            :event-types="eventTypes"
            :scope-type="scopeType"
            :editing="true"
            :busy="busyId === channel.id"
            @submit="saveEdit(channel)"
            @cancel="closeForm"
            @open-guide="openGuide"
          />
        </li>
      </ul>

      <div v-if="formMode === 'add'" class="channel-row mt-3">
        <p class="font-medium text-fg mb-2">New channel</p>
        <ChannelForm
          v-model="form"
          :platforms="platforms"
          :event-types="eventTypes"
          :scope-type="scopeType"
          :editing="false"
          :busy="busyId === 'new'"
          @submit="create"
          @cancel="closeForm"
          @open-guide="openGuide"
        />
      </div>
      <button
        v-else-if="formMode === null"
        class="btn primary mt-3"
        data-testid="add-channel"
        @click="openAdd"
      >
        Add a channel
      </button>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import ChannelForm from '@/components/notifications/ChannelForm.vue';
import ChannelSetupGuide from '@/components/notifications/ChannelSetupGuide.vue';

/**
 * Set up the chat channels for one scope (SB-1605): a squad (team + age
 * group), a club, or every match (admin). Several channels per scope, each
 * with its own platform, audience, events, invite link and pause switch.
 *
 * Platforms, their setup steps and validation patterns come from the adapter
 * registry, and event names from the API, so nothing here lists them.
 */
const props = defineProps({
  scopeType: {
    type: String,
    required: true,
    validator: v => ['club', 'team', 'global'].includes(v),
  },
  clubId: { type: Number, default: null },
  teamId: { type: Number, default: null },
  ageGroupId: { type: Number, default: null },
  heading: { type: String, default: '' },
});
const emit = defineEmits(['changed']);

// SB-1672: the setup guide, opened at the tab for what is being set up.
const guide = ref(null);
const openGuide = ({ platform, audience } = {}) => {
  const tab =
    audience === 'players'
      ? 'players'
      : platform
        ? props.scopeType === 'club'
          ? 'announce'
          : 'fans'
        : 'start';
  guide.value = { tab, platform: platform || 'slack' };
};

const authStore = useAuthStore();
const api = () => `${getApiBaseUrl()}/api`;

const platforms = ref([]);
const eventTypes = ref([]);
const channels = ref([]);
const loading = ref(true);
const loadError = ref(false);
const busyId = ref(null);
const formMode = ref(null); // null | 'add' | channel id
const form = ref(null);
const flash = ref(null);

let flashTimer = null;
const showFlash = (kind, text) => {
  flash.value = { kind, text };
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => (flash.value = null), 6000);
};

const scopeQuery = () => {
  const params = new URLSearchParams({ scope_type: props.scopeType });
  if (props.scopeType === 'club') params.set('club_id', props.clubId);
  if (props.scopeType === 'team') {
    params.set('team_id', props.teamId);
    params.set('age_group_id', props.ageGroupId);
  }
  return params.toString();
};

const fetchChannels = async () => {
  channels.value =
    (await authStore.apiRequest(
      `${api()}/notification-channels?${scopeQuery()}`
    )) || [];
};

const load = async () => {
  loading.value = true;
  loadError.value = false;
  try {
    const [p, e] = await Promise.all([
      platforms.value.length
        ? platforms.value
        : authStore.apiRequest(`${api()}/notifications/platforms`),
      eventTypes.value.length
        ? eventTypes.value
        : authStore.apiRequest(`${api()}/notification-channels/event-types`),
      fetchChannels(),
    ]);
    platforms.value = p || [];
    eventTypes.value = e || [];
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
};

const platformOf = id => platforms.value.find(p => p.id === id);
const platformLabel = id => platformOf(id)?.label || id;
const platformIcon = id => platformOf(id)?.icon || '';

// Event ids in the server's order, whatever order they were ticked in.
const inEventOrder = types => {
  const order = eventTypes.value.map(e => e.id);
  const rank = t => (order.includes(t) ? order.indexOf(t) : order.length);
  return [...types].sort((a, b) => rank(a) - rank(b));
};

const eventsSummary = types => {
  if (types === null || types === undefined) return 'Every match event';
  if (!types.length) return 'Nothing: no events are selected';
  const names = Object.fromEntries(eventTypes.value.map(e => [e.id, e.label]));
  return inEventOrder(types)
    .map(t => names[t] || t)
    .join(', ');
};

const timeAgo = iso => {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  if (Number.isNaN(seconds)) return '';
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const units = [
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size)
      return rtf.format(Math.round(seconds / size), unit);
  }
  return 'just now';
};

const deliverySummary = channel => {
  if (!channel.last_delivery_known) return 'Delivery history unavailable';
  const last = channel.last_delivery;
  if (!last) return 'Nothing posted yet';
  const when = last.at ? ` ${timeAgo(last.at)}` : '';
  if (last.status === 'failed')
    return `Failed${when}${last.error ? `: ${last.error}` : ''}`;
  if (last.status === 'pending') return `Sending${when}`;
  return `Posted${when}`;
};

const blankForm = () => ({
  platform: platforms.value[0]?.id || '',
  audience: 'fans',
  label: '',
  destination: '',
  invite_url: '',
  eventsMode: 'all',
  events: [],
  post_as_threads: false,
});

const openAdd = () => {
  form.value = blankForm();
  formMode.value = 'add';
};

const openEdit = channel => {
  form.value = {
    platform: channel.platform,
    audience: channel.audience,
    label: channel.label || '',
    destination: '',
    invite_url: channel.invite_url || '',
    eventsMode: channel.event_types === null ? 'all' : 'some',
    events: [...(channel.event_types || [])],
    post_as_threads: Boolean(channel.post_as_threads),
  };
  formMode.value = channel.id;
};

const closeForm = () => {
  formMode.value = null;
  form.value = null;
};

// null = every event; [] = none. Never collapse the two.
const eventTypesOf = f =>
  f.eventsMode === 'all' ? null : inEventOrder(f.events);

const run = async (id, fn) => {
  busyId.value = id;
  try {
    await fn();
    return true;
  } catch (err) {
    showFlash('error', err.message || 'Something went wrong');
    return false;
  } finally {
    busyId.value = null;
  }
};

const changed = async () => {
  await fetchChannels().catch(() => {});
  emit('changed');
};

const create = async () => {
  const f = form.value;
  const body = {
    scope_type: props.scopeType,
    club_id: props.scopeType === 'club' ? props.clubId : null,
    team_id: props.scopeType === 'team' ? props.teamId : null,
    age_group_id: props.scopeType === 'team' ? props.ageGroupId : null,
    audience: props.scopeType === 'global' ? 'fans' : f.audience,
    platform: f.platform,
    destination: f.destination.trim(),
    label: f.label.trim() || null,
    invite_url: f.invite_url.trim() || null,
    event_types: eventTypesOf(f),
    post_as_threads: Boolean(f.post_as_threads),
  };
  const ok = await run('new', () =>
    authStore.apiRequest(`${api()}/notification-channels`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  );
  if (ok) {
    closeForm();
    showFlash('success', 'Channel added. Send a test to check it.');
    await changed();
  }
};

const saveEdit = async channel => {
  const f = form.value;
  const body = {
    label: f.label.trim() || null,
    invite_url: f.invite_url.trim() || null,
    event_types: eventTypesOf(f),
    post_as_threads: Boolean(f.post_as_threads),
  };
  if (f.destination.trim()) body.destination = f.destination.trim();
  const ok = await run(channel.id, () =>
    authStore.apiRequest(`${api()}/notification-channels/${channel.id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    })
  );
  if (ok) {
    closeForm();
    showFlash('success', 'Channel saved.');
    await changed();
  }
};

const setEnabled = async (channel, enabled) => {
  const ok = await run(channel.id, () =>
    authStore.apiRequest(`${api()}/notification-channels/${channel.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    })
  );
  if (ok)
    showFlash(
      'success',
      enabled ? 'Channel resumed.' : 'Channel paused. Its settings are kept.'
    );
  await changed();
};

const sendTest = async channel => {
  let result = null;
  await run(channel.id, async () => {
    result = await authStore.apiRequest(
      `${api()}/notification-channels/${channel.id}/test`,
      { method: 'POST' }
    );
  });
  if (!result) return;
  if (result.success)
    showFlash('success', 'Test message sent. Check the channel.');
  else showFlash('error', `Test failed: ${result.error || 'unknown error'}`);
};

const remove = async channel => {
  const name = channel.label || `${platformLabel(channel.platform)} channel`;
  if (
    !confirm(
      `Remove "${name}"? Missing Table stops posting there, and people who joined through it lose the link.`
    )
  )
    return;
  const ok = await run(channel.id, () =>
    authStore.apiRequest(`${api()}/notification-channels/${channel.id}`, {
      method: 'DELETE',
    })
  );
  if (ok) {
    showFlash('success', 'Channel removed.');
    await changed();
  }
};

watch(
  () => [props.scopeType, props.clubId, props.teamId, props.ageGroupId],
  () => {
    closeForm();
    load();
  }
);

onMounted(load);
</script>

<style scoped>
.channel-row {
  border: 1px solid rgb(var(--color-line));
  border-radius: 0.5rem;
  padding: 1rem;
  background: rgb(var(--color-card));
}
.details {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.25rem 0.75rem;
  margin-top: 0.75rem;
  font-size: 0.8125rem;
}
.details dt {
  color: rgb(var(--color-fg-muted));
}
.details dd {
  color: rgb(var(--color-fg));
  min-width: 0;
  overflow-wrap: anywhere;
}
.warn-text {
  color: #b45309;
}
.pill {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
}
.pill.paused {
  background: #fef3c7;
  color: #92400e;
}
.pill.threads {
  background: #e0e7ff;
  color: #3730a3;
}
.link {
  color: #2563eb;
  text-decoration: underline;
}
.link-btn {
  margin-left: 0.5rem;
  color: #2563eb;
  text-decoration: underline;
}
.btn {
  padding: 0.4rem 0.8rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.primary {
  background: #2563eb;
  color: #fff;
}
.btn.secondary {
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  border-color: rgb(var(--color-line));
}
.btn.danger {
  background: transparent;
  color: #b91c1c;
  border-color: #fecaca;
}
.flash {
  padding: 0.625rem 0.875rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
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

/* `:global(.dark .x)`, never `:global(.dark) .x`, which compiles to `.dark`. */
:global(.dark .channel-manager .warn-text) {
  color: #fcd34d;
}
:global(.dark .channel-manager .pill.paused) {
  background: rgb(245 158 11 / 0.15);
  color: #fcd34d;
}
:global(.dark .channel-manager .pill.threads) {
  background: rgb(99 102 241 / 0.18);
  color: #c7d2fe;
}
:global(.dark .channel-manager .link),
:global(.dark .channel-manager .link-btn) {
  color: #93c5fd;
}
:global(.dark .channel-manager .btn.danger) {
  color: #fca5a5;
  border-color: rgb(248 113 113 / 0.4);
}
:global(.dark .channel-manager .flash.success) {
  background: rgb(16 185 129 / 0.15);
  color: #6ee7b7;
  border-color: rgb(16 185 129 / 0.35);
}
:global(.dark .channel-manager .flash.error) {
  background: rgb(248 113 113 / 0.12);
  color: #fca5a5;
  border-color: rgb(248 113 113 / 0.35);
}
</style>
