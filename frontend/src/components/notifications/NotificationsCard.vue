<template>
  <section class="notifications-card" data-testid="notifications-card">
    <header class="notifications-header">
      <h3>Notifications</h3>
      <p class="notifications-subhead">
        Get a push when a team you follow scores, kicks off, hits halftime, or
        finishes.
      </p>
    </header>

    <!-- iOS-not-standalone gate -->
    <div v-if="isIosBlocked" class="notifications-banner banner-warn">
      <strong>Install MT to your home screen first.</strong>
      <span>
        iOS requires the app to be installed before notifications can be
        enabled. Use Share → "Add to Home Screen" in Safari, then come back
        here.
      </span>
    </div>

    <!-- Permission denied -->
    <div v-else-if="isBlocked" class="notifications-banner banner-error">
      <strong>Notifications blocked.</strong>
      <span>
        Open your browser's site settings for missingtable.com and allow
        notifications, then refresh.
      </span>
    </div>

    <!-- Unsupported browser -->
    <div v-else-if="!isSupported" class="notifications-banner banner-muted">
      <strong>Not supported on this browser.</strong>
      <span>Try Chrome, Edge, Firefox, or Safari 16.4+.</span>
    </div>

    <!-- Main control: enable / enabled state -->
    <div v-else class="notifications-body">
      <button
        v-if="!isEnabled"
        class="enable-button"
        :disabled="loading"
        @click="onEnable"
      >
        {{ loading ? 'Enabling…' : 'Enable push notifications on this device' }}
      </button>

      <div v-else class="enabled-block">
        <div class="enabled-pill">
          <span class="enabled-dot" aria-hidden="true"></span>
          Notifications enabled on this device
        </div>
        <button class="test-button" :disabled="loading" @click="onTest">
          {{ loading ? 'Sending…' : 'Send test notification' }}
        </button>
      </div>

      <p v-if="lastError" class="notifications-error">{{ lastError }}</p>
      <p v-if="lastMessage" class="notifications-success">{{ lastMessage }}</p>
    </div>

    <!-- Manage devices -->
    <div v-if="isSupported && subscriptions.length" class="manage-section">
      <h4>Devices receiving notifications</h4>
      <ul class="device-list">
        <li v-for="sub in subscriptions" :key="sub.id" class="device-item">
          <div>
            <div class="device-label">
              {{ sub.device_label || 'Unknown device' }}
            </div>
            <div class="device-meta">
              Last seen {{ formatDate(sub.last_seen_at) }}
            </div>
          </div>
          <button
            class="revoke-button"
            :disabled="loading"
            @click="onRevoke(sub.id)"
          >
            Revoke
          </button>
        </li>
      </ul>
    </div>

    <!-- Notification preferences (SB-57) -->
    <div v-if="isSupported" class="preferences-section">
      <h4>What to notify me about</h4>
      <ul class="preferences-list">
        <li class="preference-item">
          <label class="preference-label">
            <input
              type="checkbox"
              class="preference-checkbox"
              :checked="preferences.kickoff"
              :disabled="!preferencesLoaded"
              data-testid="pref-toggle-kickoff"
              @change="onTogglePref('kickoff', $event.target.checked)"
            />
            <span class="preference-name">Kickoff</span>
          </label>
        </li>
        <li class="preference-item">
          <label class="preference-label">
            <input
              type="checkbox"
              class="preference-checkbox"
              :checked="preferences.goal"
              :disabled="!preferencesLoaded"
              data-testid="pref-toggle-goal"
              @change="onTogglePref('goal', $event.target.checked)"
            />
            <span class="preference-name">Goals</span>
          </label>
        </li>
        <li class="preference-item">
          <label class="preference-label">
            <input
              type="checkbox"
              class="preference-checkbox"
              :checked="preferences.halftime"
              :disabled="!preferencesLoaded"
              data-testid="pref-toggle-halftime"
              @change="onTogglePref('halftime', $event.target.checked)"
            />
            <span class="preference-name">Halftime</span>
          </label>
        </li>
        <li class="preference-item">
          <label class="preference-label">
            <input
              type="checkbox"
              class="preference-checkbox"
              :checked="preferences.fulltime"
              :disabled="!preferencesLoaded"
              data-testid="pref-toggle-fulltime"
              @change="onTogglePref('fulltime', $event.target.checked)"
            />
            <span class="preference-name">Fulltime</span>
          </label>
        </li>
        <li class="preference-item">
          <label class="preference-label">
            <input
              type="checkbox"
              class="preference-checkbox"
              :checked="cardsEnabled"
              :disabled="!preferencesLoaded"
              data-testid="pref-toggle-cards"
              @change="onToggleCards($event.target.checked)"
            />
            <span class="preference-name">Cards (yellow + red)</span>
          </label>
        </li>
      </ul>
      <p v-if="preferencesError" class="notifications-error">
        Couldn't save preference: {{ preferencesError }}
      </p>
    </div>

    <!-- Followed teams (read-only summary) -->
    <div v-if="isSupported" class="follows-section">
      <h4>Teams you follow</h4>
      <p v-if="!follows.length" class="follows-empty">
        You aren't following any teams yet. Open a team page and tap "Follow" to
        start getting notifications for them.
      </p>
      <ul v-else class="follows-list">
        <li
          v-for="f in follows"
          :key="f.team_id"
          class="follow-item"
          :data-testid="`follow-item-${f.team_id}`"
        >
          <div class="follow-item-main">
            <span class="follow-team" data-testid="follow-label-primary">{{
              followPrimaryLabel(f)
            }}</span>
            <span class="follow-item-sub" data-testid="follow-label-sub">
              Showing all age groups
            </span>
          </div>
          <span
            v-if="
              f.team?.club?.name && f.team.club.name !== (f.team?.name || '')
            "
            class="follow-club"
          >
            {{ f.team.club.name }}
          </span>
        </li>
      </ul>
    </div>

    <!-- Followed brackets (tournament + group + age group) -->
    <div v-if="isSupported" class="follows-section">
      <h4>Brackets you follow</h4>
      <p v-if="!bracketFollows.length" class="follows-empty">
        You aren't following any tournament brackets yet. Open a tournament's
        Bracket or Standings view and tap "Follow this bracket" to get a push at
        full time for every match in it.
      </p>
      <ul v-else class="follows-list">
        <li
          v-for="b in bracketFollows"
          :key="`${b.tournament_id}:${b.tournament_group}:${b.age_group_id}`"
          class="follow-item"
          :data-testid="`bracket-follow-item-${b.tournament_id}-${b.age_group_id}`"
        >
          <div class="follow-item-main">
            <span class="follow-team">{{ bracketPrimaryLabel(b) }}</span>
            <span class="follow-item-sub">Full-time scores only</span>
          </div>
          <button
            class="revoke-button"
            :disabled="bracketLoading"
            @click="onUnfollowBracket(b)"
          >
            Unfollow
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { usePushNotifications } from '../../composables/usePushNotifications';
import { useTeamFollows } from '../../composables/useTeamFollows';
import { useBracketFollows } from '../../composables/useBracketFollows';
import { useNotificationPreferences } from '../../composables/useNotificationPreferences';

const {
  isSupported,
  isEnabled,
  isBlocked,
  isIosBlocked,
  loading,
  lastError,
  enable,
  disable,
  listSubscriptions,
  sendTest,
} = usePushNotifications();

// Shared singleton (SB-55): same `follows` reactive list every FollowButton mutates.
const { follows, refresh: refreshFollows } = useTeamFollows();

// Bracket follows (tournament + group + age group). Same singleton the
// tournament-page toggle mutates, so unfollowing here updates that toggle too.
const {
  follows: bracketFollows,
  loading: bracketLoading,
  ensureLoaded: ensureBracketFollowsLoaded,
  unfollow: unfollowBracket,
} = useBracketFollows();

// Per-event preferences (SB-57).
const {
  preferences,
  cardsEnabled,
  loaded: preferencesLoaded,
  error: preferencesError,
  ensureLoaded: ensurePreferencesLoaded,
  setPreference,
  setCards,
} = useNotificationPreferences();

const subscriptions = ref([]);
const lastMessage = ref('');

async function refresh() {
  if (!isSupported.value) return;
  const [subs] = await Promise.all([
    listSubscriptions(),
    refreshFollows(),
    ensureBracketFollowsLoaded(),
    ensurePreferencesLoaded(),
  ]);
  subscriptions.value = subs;
}

// "2026 National Academy Championships · Bracket A · U14"
function bracketPrimaryLabel(b) {
  const tourney = b.tournament?.name || `Tournament #${b.tournament_id}`;
  const age = b.age_group?.name;
  const parts = [tourney, b.tournament_group];
  if (age) parts.push(age);
  return parts.join(' · ');
}

async function onUnfollowBracket(b) {
  await unfollowBracket(b.tournament_id, b.tournament_group, b.age_group_id);
}

async function onTogglePref(eventType, enabled) {
  await setPreference(eventType, enabled);
}

async function onToggleCards(enabled) {
  await setCards(enabled);
}

// SB-65: disambiguate follow rows. For MLS Next teams the team name often
// equals the club name (e.g. "IFA / IFA"), making the list look like it's
// about clubs. Append the league + division when we have them.
function followPrimaryLabel(f) {
  const name = f.team?.name || `Team #${f.team_id}`;
  const league = f.team?.division?.leagues?.name;
  const division = f.team?.division?.name;
  const parts = [name];
  if (league) parts.push(league);
  if (division) parts.push(division);
  return parts.join(' · ');
}

async function onEnable() {
  lastMessage.value = '';
  const result = await enable();
  if (result.success) {
    lastMessage.value = 'Notifications are now enabled on this device.';
    await refresh();
  }
}

async function onTest() {
  lastMessage.value = '';
  const result = await sendTest();
  if (result.success) {
    const sent = result.data?.sent ?? 0;
    const failed = result.data?.failed ?? 0;
    lastMessage.value =
      sent > 0
        ? `Test sent to ${sent} device${sent === 1 ? '' : 's'}.`
        : failed > 0
          ? `Test failed on all ${failed} device${failed === 1 ? '' : 's'} — check the device-list status above.`
          : 'No devices registered yet.';
  }
}

async function onRevoke(subscriptionId) {
  lastMessage.value = '';
  const result = await disable(subscriptionId);
  if (result.success) {
    lastMessage.value = 'Device removed.';
    await refresh();
  }
}

function formatDate(iso) {
  if (!iso) return 'unknown';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

onMounted(refresh);
</script>

<style scoped>
.notifications-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
}

.notifications-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.notifications-subhead {
  margin: 0 0 16px;
  font-size: 14px;
  color: #6b7280;
  line-height: 1.4;
}

.notifications-banner {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.4;
  margin-bottom: 12px;
}

.notifications-banner strong {
  font-weight: 700;
}

.banner-warn {
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
}

.banner-error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.banner-muted {
  background: #f3f4f6;
  color: #4b5563;
  border: 1px solid #e5e7eb;
}

.notifications-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.enable-button {
  background: #0257fe;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 12px 18px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  transition: background-color 0.15s ease;
}

.enable-button:hover:not(:disabled) {
  background: #0047d4;
}

.enable-button:disabled {
  background: #93c5fd;
  cursor: not-allowed;
}

.enabled-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.enabled-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
  align-self: flex-start;
}

.enabled-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18);
}

.test-button {
  background: transparent;
  color: #0257fe;
  border: 1.5px solid #0257fe;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
  min-height: 40px;
  transition: background-color 0.15s ease;
}

.test-button:hover:not(:disabled) {
  background: rgba(2, 87, 254, 0.08);
}

.test-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.notifications-error {
  margin: 4px 0 0;
  font-size: 13px;
  color: #991b1b;
}

.notifications-success {
  margin: 4px 0 0;
  font-size: 13px;
  color: #065f46;
}

.manage-section,
.follows-section,
.preferences-section {
  margin-top: 20px;
  border-top: 1px solid #f3f4f6;
  padding-top: 16px;
}

/* Notification preferences (SB-57) */
.preferences-section h4 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.preferences-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preference-item {
  padding: 0;
}

.preference-label {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  min-height: 44px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.preference-label:hover {
  background: #f9fafb;
}

.preference-checkbox {
  width: 20px;
  height: 20px;
  margin: 0;
  cursor: pointer;
  accent-color: #0257fe;
  flex-shrink: 0;
}

.preference-checkbox:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.preference-name {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}

.manage-section h4,
.follows-section h4 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.device-list,
.follows-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.device-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.device-label {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.device-meta {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

.revoke-button {
  background: transparent;
  color: #b91c1c;
  border: 1.5px solid #b91c1c;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  min-height: 36px;
}

.revoke-button:hover:not(:disabled) {
  background: rgba(185, 28, 28, 0.08);
}

.revoke-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.follows-empty {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.4;
}

.follow-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 14px;
}

.follow-item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.follow-team {
  font-weight: 600;
  color: #111827;
  /* Allow the primary label (which now includes league + division) to wrap
     on narrow viewports instead of overflowing. */
  word-break: break-word;
}

.follow-item-sub {
  font-size: 12px;
  color: #6b7280;
  font-weight: 400;
}

.follow-club {
  font-size: 12px;
  color: #9ca3af;
  flex-shrink: 0;
}
</style>
