<template>
  <section class="access-panel" data-testid="access-panel">
    <h4 class="panel-title">Who's in</h4>

    <p v-if="loadError" class="panel-msg" data-testid="access-error">
      Requests are unavailable right now.
    </p>

    <template v-else>
      <!-- Requests -->
      <div class="block" data-testid="requests-block">
        <p class="block-title">
          Requests<span v-if="requests.length"> ({{ requests.length }})</span>
        </p>
        <p v-if="!requests.length" class="panel-msg" data-testid="no-requests">
          No one is waiting.
        </p>
        <ul v-else class="people">
          <li
            v-for="r in requests"
            :key="`${r.channel_id}-${r.user_id}`"
            class="person"
            :data-testid="`request-${r.user_id}`"
          >
            <div class="who">
              <span class="name">{{ r.display_name || 'Someone' }}</span>
              <span class="meta">
                {{ channelLabel(r) }} · asked {{ formatDate(r.requested_at) }}
              </span>
            </div>
            <div class="actions">
              <button
                class="btn primary"
                :disabled="busy"
                data-testid="approve-btn"
                @click="decide(r, 'active')"
              >
                Approve
              </button>
              <button
                class="btn"
                :disabled="busy"
                data-testid="deny-btn"
                @click="decide(r, 'denied')"
              >
                Deny
              </button>
            </div>
          </li>
        </ul>
      </div>

      <!-- What to do on the platform after a decision -->
      <p v-if="notice" class="notice" data-testid="platform-notice">
        {{ notice }}
      </p>
      <p v-if="actionError" class="error" data-testid="access-action-error">
        {{ actionError }}
      </p>

      <!-- Members -->
      <div class="block" data-testid="members-block">
        <p class="block-title">
          Members<span v-if="members.length"> ({{ members.length }})</span>
        </p>
        <p v-if="!members.length" class="panel-msg" data-testid="no-members">
          No one has been given a link yet.
        </p>
        <ul v-else class="people">
          <li
            v-for="m in members"
            :key="`${m.channel_id}-${m.user_id}`"
            class="person"
            :data-testid="`member-${m.user_id}`"
          >
            <div class="who">
              <span class="name">{{ m.display_name || 'Someone' }}</span>
              <span class="meta">
                {{ channelLabel(m) }} · {{ sourceLabel(m.source) }}
              </span>
            </div>
            <div class="actions">
              <button
                class="btn danger"
                :disabled="busy"
                data-testid="revoke-btn"
                @click="decide(m, 'revoked')"
              >
                Revoke
              </button>
            </div>
          </li>
        </ul>
      </div>

      <!-- Invite a fan -->
      <div v-if="fanChannels.length" class="block" data-testid="invite-block">
        <p class="block-title">Invite a fan</p>
        <div class="invite-row">
          <select
            v-if="fanChannels.length > 1"
            v-model.number="inviteChannelId"
            data-testid="invite-channel"
          >
            <option v-for="c in fanChannels" :key="c.id" :value="c.id">
              {{ channelLabel(c) }}
            </option>
          </select>
          <select
            v-model="inviteUserId"
            :disabled="!candidates.length"
            data-testid="invite-person"
          >
            <option value="">
              {{ candidates.length ? 'Choose a fan' : 'No fans to invite' }}
            </option>
            <option v-for="p in candidates" :key="p.user_id" :value="p.user_id">
              {{ p.display_name || 'Unnamed fan' }}
            </option>
          </select>
          <button
            class="btn primary"
            :disabled="busy || !inviteUserId"
            data-testid="invite-btn"
            @click="invite"
          >
            Invite
          </button>
        </div>
        <p class="hint">
          They will see the invite link on their profile. Only fans of this club
          who don't have access yet are listed.
        </p>
      </div>
    </template>
  </section>
</template>

<script setup>
/**
 * A manager's review of a team's chat channels (SB-1671): pending requests to
 * approve or deny, members to revoke, and fans to invite.
 *
 * Missing Table only decides who sees a channel's invite link. Admitting or
 * removing someone in Slack, Discord or Telegram is still the manager's job,
 * so every decision ends with what to do there.
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

const props = defineProps({
  teamId: { type: Number, required: true },
  // The team's squad fan channels with an invite link: { id, platform,
  // platform_label, age_group_name }. Inviting to a channel without a link
  // would give the fan nothing to open.
  fanChannels: { type: Array, default: () => [] },
});
const emit = defineEmits(['changed']);

const authStore = useAuthStore();
const base = () => `${getApiBaseUrl()}/api`;

const requests = ref([]);
const members = ref([]);
const candidates = ref([]);
const loadError = ref(false);
const busy = ref(false);
const notice = ref('');
const actionError = ref('');
const inviteChannelId = ref(null);
const inviteUserId = ref('');

const PLATFORM_LABELS = {
  slack: 'Slack',
  discord: 'Discord',
  telegram: 'Telegram',
};
const platformName = p => PLATFORM_LABELS[p] || p;

// The step on the platform that MT cannot do for the manager.
const AFTER_APPROVE = {
  slack: name =>
    `Now add ${name} to the private Slack channel. The invite link only gets them into the workspace.`,
  discord: name =>
    `Now give ${name} the squad's role in Discord. The invite link only gets them into the server.`,
  telegram: name =>
    `If your Telegram link asks for approval, approve ${name} in Telegram when they ask to join.`,
};

const channelLabel = row => {
  const squad = row.age_group_name || 'Team';
  const audience = row.audience === 'players' ? 'players' : 'fans';
  return `${squad} ${audience} · ${row.platform_label || platformName(row.platform)}`;
};

const sourceLabel = source =>
  ({
    request: 'approved request',
    invite: 'invited',
    eligible: 'joined',
  })[source] || 'has access';

const formatDate = iso => {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

const fanChannelIds = computed(() => props.fanChannels.map(c => c.id));

const load = async () => {
  loadError.value = false;
  try {
    const q = `?team_id=${props.teamId}`;
    const [reqs, mems] = await Promise.all([
      authStore.apiRequest(`${base()}/channels/requests${q}`),
      authStore.apiRequest(`${base()}/channels/members${q}`),
    ]);
    requests.value = reqs || [];
    members.value = mems || [];
  } catch {
    loadError.value = true;
  }
};

const loadCandidates = async () => {
  inviteUserId.value = '';
  candidates.value = [];
  if (!inviteChannelId.value) return;
  try {
    candidates.value =
      (await authStore.apiRequest(
        `${base()}/channels/${inviteChannelId.value}/candidates`
      )) || [];
  } catch {
    candidates.value = [];
  }
};

const decide = async (row, status) => {
  busy.value = true;
  notice.value = '';
  actionError.value = '';
  const name = row.display_name || 'them';
  try {
    await authStore.apiRequest(
      `${base()}/channels/${row.channel_id}/members/${row.user_id}`,
      { method: 'PUT', body: JSON.stringify({ status }) }
    );
    if (status === 'active') {
      notice.value = (AFTER_APPROVE[row.platform] || (() => ''))(name);
    } else if (status === 'revoked') {
      notice.value = `${name} no longer sees the link. If they already joined, remove them in ${platformName(row.platform)} too.`;
    }
    await Promise.all([load(), loadCandidates()]);
    emit('changed');
  } catch (err) {
    actionError.value = err.message || 'Something went wrong';
  } finally {
    busy.value = false;
  }
};

const invite = async () => {
  const channel = props.fanChannels.find(c => c.id === inviteChannelId.value);
  const person = candidates.value.find(p => p.user_id === inviteUserId.value);
  if (!channel || !person) return;
  await decide(
    {
      channel_id: channel.id,
      user_id: person.user_id,
      display_name: person.display_name,
      platform: channel.platform,
    },
    'active'
  );
};

watch(
  fanChannelIds,
  ids => {
    if (!ids.includes(inviteChannelId.value)) {
      inviteChannelId.value = ids[0] ?? null;
    }
  },
  { immediate: true }
);
watch(inviteChannelId, loadCandidates);
watch(() => props.teamId, load);
onMounted(() => {
  load();
  loadCandidates();
});
</script>

<style scoped>
.access-panel {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 8px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--color-fg));
  margin: 0 0 8px;
}

.block {
  margin-top: 12px;
}

.block-title {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--color-fg));
  margin: 0 0 6px;
}

.panel-msg,
.hint {
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
  margin: 0;
}

.hint {
  margin-top: 6px;
}

.people {
  list-style: none;
  margin: 0;
  padding: 0;
}

.person {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-top: 1px solid rgb(var(--color-line));
}

.person:first-child {
  border-top: none;
}

.who {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.name {
  font-size: 14px;
  color: rgb(var(--color-fg));
}

.meta {
  font-size: 12px;
  color: rgb(var(--color-fg-muted));
}

.actions,
.invite-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.invite-row select {
  padding: 4px 8px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  max-width: 100%;
}

.btn {
  padding: 4px 10px;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  cursor: pointer;
}

.btn.primary {
  background: rgb(37 99 235);
  border-color: rgb(37 99 235);
  color: #fff;
}

.btn.danger {
  color: rgb(220 38 38);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.notice {
  margin: 10px 0 0;
  padding: 8px 10px;
  font-size: 13px;
  border-radius: 6px;
  background: rgb(37 99 235 / 0.08);
  color: rgb(var(--color-fg));
}

.error {
  margin: 8px 0 0;
  font-size: 13px;
  color: rgb(220 38 38);
}
</style>
