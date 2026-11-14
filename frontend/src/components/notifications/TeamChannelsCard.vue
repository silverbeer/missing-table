<template>
  <section
    v-if="loaded"
    id="team-channels"
    class="team-channels-card"
    data-testid="team-channels-card"
  >
    <h3 class="card-title" data-testid="channels-title">
      Community channels{{ clubName ? ` for ${clubName}` : '' }}
    </h3>
    <p class="card-note" data-testid="channels-community-note">
      Run by your club's managers, not by Missing Table. MT only posts match
      updates. Invite links can be passed on, so anyone with one can join.
    </p>

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
          <span
            v-if="channel.age_note"
            class="channel-age"
            data-testid="channel-age-note"
          >
            {{ channel.age_note }}
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
      link{{
        canSetUp
          ? '.'
          : teamId && squads
            ? ", and this team isn't registered in an age group yet."
            : ": set channels up from your team's page, or the club ones from your profile."
      }}
    </p>

    <p v-else-if="awaitingLink" class="card-msg" data-testid="awaiting-link">
      Your club's chat channels are being set up. Check back soon.
    </p>

    <p v-else class="card-msg" data-testid="member-empty">
      No chat channels yet. Ask your team manager to set one up.
    </p>

    <p v-if="actionError" class="error-msg" data-testid="action-error">
      {{ actionError }}
    </p>

    <!-- SB-1605: the team manager's way in. The server says who may manage. -->
    <div v-if="canSetUp" class="manage-block">
      <button
        v-if="!managing"
        class="action-btn"
        data-testid="manage-btn"
        @click="managing = true"
      >
        Manage chat channels
        <span
          v-if="pendingCount"
          class="pending-badge"
          data-testid="pending-badge"
        >
          {{ pendingCount }} {{ pendingCount === 1 ? 'request' : 'requests' }}
        </span>
      </button>
      <template v-else>
        <label v-if="squads.length > 1" class="squad-picker">
          Squad
          <select v-model.number="squadId" data-testid="squad-picker">
            <option v-for="s in squads" :key="s.id" :value="s.id">
              {{ s.name }}
            </option>
          </select>
        </label>
        <ChannelAccessPanel
          :team-id="teamId"
          :fan-channels="squadFanChannels"
          @changed="load"
        />
        <ChannelManager
          scope-type="team"
          :team-id="teamId"
          :age-group-id="squadId"
          :heading="`${squadName} chat channels`"
          @changed="load"
        />
        <button
          class="link-btn mt-3"
          data-testid="manage-done"
          @click="managing = false"
        >
          Done
        </button>
      </template>
    </div>
  </section>
</template>

<script>
import { computed, ref, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import ChannelManager from '@/components/notifications/ChannelManager.vue';
import ChannelAccessPanel from '@/components/notifications/ChannelAccessPanel.vue';

/**
 * The chat channels a viewer may join (SB-1609), from /api/me/channels.
 *
 * The server decides everything: which channels exist for this viewer (fans
 * never see player channels, players never see fan or club fan channels, U13
 * has none), and each one's state. Platform names come from the response, so
 * a new platform needs no change here.
 *
 * With `teamId` (the My Club page) it shows that team's channels; without, the
 * viewer's own team and club. With `teamId`, a manager can also set up each
 * squad's channels here: the server lists the team's age groups, and
 * `ageGroupId`, when the page knows one, is picked first.
 */
export default {
  name: 'TeamChannelsCard',
  components: { ChannelManager, ChannelAccessPanel },
  props: {
    teamId: { type: Number, default: null },
    ageGroupId: { type: Number, default: null },
  },
  setup(props) {
    const authStore = useAuthStore();
    const loaded = ref(false);
    const loadError = ref(false);
    const channels = ref([]);
    const hasTeam = ref(false);
    const managed = ref(null);
    const canManage = ref(false);
    const clubName = ref(null);
    const busyId = ref(null);
    const actionError = ref('');
    const managing = ref(false);
    // The team's squads, sent only to someone who can manage it. null = not
    // sent (or unknown); [] = registered in no age group.
    const squads = ref(null);
    // SB-1671: enabled channels the viewer could see once they get an invite
    // link, and the manager's pending request count.
    const awaitingLink = ref(0);
    const pendingCount = ref(0);
    const squadId = ref(null);
    const squadName = computed(
      () => squads.value?.find(s => s.id === squadId.value)?.name || 'Squad'
    );
    const canSetUp = computed(
      () => canManage.value && Boolean(props.teamId && squads.value?.length)
    );

    const base = () => `${getApiBaseUrl()}/api`;

    const load = async () => {
      loadError.value = false;
      try {
        const query = props.teamId ? `?team_id=${props.teamId}` : '';
        const data = await authStore.apiRequest(
          `${base()}/me/channels${query}`
        );
        channels.value = data?.channels || [];
        clubName.value = data?.club_name || null;
        hasTeam.value = Boolean(data?.has_team);
        managed.value = data?.managed ?? null;
        canManage.value = Boolean(data?.can_manage);
        squads.value = data?.age_groups ?? null;
        awaitingLink.value = data?.awaiting_link || 0;
        const ids = (squads.value || []).map(s => s.id);
        if (!ids.includes(squadId.value)) {
          squadId.value = ids.includes(props.ageGroupId)
            ? props.ageGroupId
            : (ids[0] ?? null);
        }
      } catch {
        loadError.value = true;
      } finally {
        loaded.value = true;
      }
      await loadPending();
    };

    // The badge on "Manage chat channels". A failure just hides it.
    const loadPending = async () => {
      if (!canSetUp.value) {
        pendingCount.value = 0;
        return;
      }
      try {
        const reqs = await authStore.apiRequest(
          `${base()}/channels/requests?team_id=${props.teamId}`
        );
        pendingCount.value = (reqs || []).length;
      } catch {
        pendingCount.value = 0;
      }
    };

    // This team's squad fan channels a fan could be invited to.
    const squadFanChannels = computed(() =>
      channels.value.filter(
        c =>
          c.scope_type === 'team' &&
          c.audience === 'fans' &&
          c.team_id === props.teamId
      )
    );

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
      clubName,
      busyId,
      actionError,
      managing,
      squads,
      squadId,
      squadName,
      canSetUp,
      awaitingLink,
      pendingCount,
      squadFanChannels,
      load,
      act,
      withdraw,
      scopeLabel,
      audienceLabel,
    };
  },
};
</script>

<style scoped>
.squad-picker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: rgb(var(--color-fg));
  margin-bottom: 12px;
}

.squad-picker select {
  padding: 4px 8px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
}

.pending-badge {
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: rgb(220 38 38);
  color: #fff;
}

.manage-block {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgb(var(--color-line));
}

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

.card-note {
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
  margin: -6px 0 12px;
  line-height: 1.4;
}

.channel-age {
  font-size: 12px;
  color: rgb(var(--color-fg-muted));
  font-style: italic;
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

/* Phones (SB-1675) */
@media (max-width: 640px) {
  .team-channels-card {
    padding: 16px;
    margin-top: 12px;
  }
}
</style>
