<template>
  <section
    v-if="loaded"
    id="team-channels"
    class="team-channels-card"
    data-testid="team-channels-card"
  >
    <h3 class="card-title">Team chat channels</h3>

    <p v-if="loadError" class="card-msg" data-testid="channels-error">
      Channels are unavailable right now.
    </p>

    <ul v-else-if="channels.length" class="channel-list">
      <li
        v-for="channel in channels"
        :key="channel.id"
        class="channel-row"
        :data-testid="`channel-${channel.id}`"
      >
        <div class="channel-info">
          <span class="channel-name">{{ scopeLabel(channel) }}</span>
          <span class="channel-meta">
            {{ audienceLabel(channel) }} · {{ channel.platform_label }}
          </span>
        </div>

        <div class="channel-action">
          <!-- MT cannot tell whether someone used the link, so this is never
               "Joined": only that the link is theirs to open. -->
          <a
            v-if="channel.state === 'member' && channel.invite_url"
            :href="channel.invite_url"
            target="_blank"
            rel="noopener noreferrer"
            class="action-btn primary"
            data-testid="open-link"
          >
            Open in {{ channel.platform_label }}
          </a>
          <button
            v-else-if="channel.state === 'can_join'"
            class="action-btn primary"
            :disabled="busyId === channel.id"
            data-testid="join-btn"
            @click="act(channel, 'join')"
          >
            Join
          </button>
          <button
            v-else-if="channel.state === 'can_request'"
            class="action-btn primary"
            :disabled="busyId === channel.id"
            data-testid="request-btn"
            @click="act(channel, 'request')"
          >
            Request invite
          </button>
          <template v-else-if="channel.state === 'requested'">
            <span class="status-text" data-testid="pending">
              Request pending
            </span>
            <button
              class="link-btn"
              :disabled="busyId === channel.id"
              data-testid="withdraw-btn"
              @click="withdraw(channel)"
            >
              Withdraw
            </button>
          </template>
          <span v-else class="status-text" data-testid="ask-manager">
            Ask a manager about this channel
          </span>
        </div>
      </li>
    </ul>

    <p v-else-if="!hasTeam" class="card-msg" data-testid="no-team">
      Channels show up here once you belong to a club or team.
    </p>

    <p v-else-if="managed === false" class="card-msg" data-testid="unclaimed">
      No one manages this team on MissingTable yet, so it has no chat channels.
      If you are its manager, ask for an invite to claim it.
    </p>

    <p v-else-if="canManage" class="card-msg" data-testid="manager-empty">
      No chat channels to join yet. A channel appears here once it has an invite
      link.
    </p>

    <p v-else class="card-msg" data-testid="member-empty">
      No chat channels yet. Ask your team manager to set one up.
    </p>

    <p v-if="actionError" class="error-msg" data-testid="action-error">
      {{ actionError }}
    </p>
  </section>
</template>

<script>
import { ref, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

/**
 * The chat channels a viewer may join (SB-1609), from /api/me/channels.
 *
 * The server decides everything: which channels exist for this viewer (fans
 * never see player channels, players never see fan or club fan channels, U13
 * has none), and each one's state. Platform names come from the response, so
 * a new platform needs no change here.
 *
 * With `teamId` (the My Club page) it shows that team's channels; without, the
 * viewer's own team and club.
 */
export default {
  name: 'TeamChannelsCard',
  props: {
    teamId: { type: Number, default: null },
  },
  setup(props) {
    const authStore = useAuthStore();
    const loaded = ref(false);
    const loadError = ref(false);
    const channels = ref([]);
    const hasTeam = ref(false);
    const managed = ref(null);
    const canManage = ref(false);
    const busyId = ref(null);
    const actionError = ref('');

    const base = () => `${getApiBaseUrl()}/api`;

    const load = async () => {
      loadError.value = false;
      try {
        const query = props.teamId ? `?team_id=${props.teamId}` : '';
        const data = await authStore.apiRequest(
          `${base()}/me/channels${query}`
        );
        channels.value = data?.channels || [];
        hasTeam.value = Boolean(data?.has_team);
        managed.value = data?.managed ?? null;
        canManage.value = Boolean(data?.can_manage);
      } catch {
        loadError.value = true;
      } finally {
        loaded.value = true;
      }
    };

    const replace = updated => {
      channels.value = channels.value.map(c =>
        c.id === updated.id ? updated : c
      );
    };

    const act = async (channel, action) => {
      actionError.value = '';
      busyId.value = channel.id;
      try {
        const updated = await authStore.apiRequest(
          `${base()}/channels/${channel.id}/${action}`,
          { method: 'POST' }
        );
        if (updated) replace(updated);
      } catch (err) {
        actionError.value = err.message || 'Something went wrong';
        await load();
      } finally {
        busyId.value = null;
      }
    };

    const withdraw = async channel => {
      actionError.value = '';
      busyId.value = channel.id;
      try {
        await authStore.apiRequest(`${base()}/channels/${channel.id}/request`, {
          method: 'DELETE',
        });
        replace({ ...channel, state: 'can_request' });
      } catch (err) {
        actionError.value = err.message || 'Something went wrong';
        await load();
      } finally {
        busyId.value = null;
      }
    };

    const scopeLabel = channel =>
      channel.scope_type === 'club' ? 'Club' : channel.age_group_name || 'Team';

    const audienceLabel = channel =>
      channel.audience === 'players' ? 'Players' : 'Fans';

    onMounted(load);
    watch(() => props.teamId, load);

    return {
      loaded,
      loadError,
      channels,
      hasTeam,
      managed,
      canManage,
      busyId,
      actionError,
      act,
      withdraw,
      scopeLabel,
      audienceLabel,
    };
  },
};
</script>

<style scoped>
.team-channels-card {
  background: rgb(var(--color-card));
  border: 1px solid rgb(var(--color-line));
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  color: rgb(var(--color-fg));
  margin: 0 0 12px;
}

.card-msg {
  font-size: 14px;
  color: rgb(var(--color-fg-muted));
  margin: 0;
  line-height: 1.5;
}

.channel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.channel-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 14px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 8px;
  background: rgb(var(--color-surface-alt));
}

.channel-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.channel-name {
  font-weight: 600;
  font-size: 14px;
  color: rgb(var(--color-fg));
}

.channel-meta {
  font-size: 12px;
  color: rgb(var(--color-fg-muted));
}

.channel-action {
  display: flex;
  align-items: center;
  gap: 10px;
}

.action-btn {
  display: inline-block;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  border: none;
  cursor: pointer;
  white-space: nowrap;
}

.action-btn.primary {
  background: #0284c7;
  color: #fff;
}

.action-btn.primary:hover:not(:disabled) {
  background: #0369a1;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.link-btn {
  background: none;
  border: none;
  padding: 0;
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
  text-decoration: underline;
  cursor: pointer;
}

.status-text {
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
}

.error-msg {
  font-size: 13px;
  color: #dc2626;
  margin: 10px 0 0;
}

:global(.dark .team-channels-card .error-msg) {
  color: #fca5a5;
}
</style>
