<template>
  <div class="live-match-view">
    <!-- Header -->
    <div class="live-header">
      <button @click="$emit('back')" class="back-button">
        <span class="back-icon">&larr;</span>
        <span class="sr-only">Back</span>
      </button>
      <div class="header-title">
        <span class="live-badge">LIVE</span>
      </div>
      <div class="connection-status" :class="{ connected: isConnected }">
        <span class="status-dot"></span>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Loading match...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container">
      <p class="error-message">{{ error }}</p>
      <button @click="fetchMatchState" class="retry-button">Retry</button>
    </div>

    <!-- Main Content -->
    <div v-else-if="matchState" class="live-content">
      <!-- Scoreboard -->
      <LiveScoreboard
        :match-state="matchState"
        :elapsed-time="clockDisplayFormatted"
        :match-period="matchPeriod"
        :is-in-stoppage="isInStoppage"
        :events="events"
      />

      <!-- Admin Controls -->
      <LiveAdminControls
        v-if="canManage"
        :match-state="matchState"
        :match-period="matchPeriod"
        :fetch-rosters="fetchTeamRosters"
        :fetch-lineups="fetchLineups"
        :save-lineup="saveLineup"
        :home-lineup="homeLineup"
        :away-lineup="awayLineup"
        :sport-type="sportType"
        @update-clock="handleUpdateClock"
        @post-goal="handlePostGoal"
        @post-card="handlePostCard"
        @reopen-match="handleReopenMatch"
      />

      <!-- Club chat rooms (SB-1330): an admin can read either club's room. -->
      <div
        v-if="chat.rooms.length > 1"
        class="room-switcher"
        role="tablist"
        data-testid="chat-room-switcher"
      >
        <button
          v-for="room in chat.rooms"
          :key="room.club_id"
          type="button"
          role="tab"
          :aria-selected="room.club_id === chat.club_id"
          :class="['room-tab', { active: room.club_id === chat.club_id }]"
          :data-testid="`chat-room-${room.club_id}`"
          @click="handleSwitchRoom(room.club_id)"
        >
          {{ room.name || 'Club' }} chat
        </button>
      </div>

      <!-- Activity Stream -->
      <ActivityStream
        :events="shownEvents"
        :can-delete="canManage"
        :home-team-id="matchState.home_team_id"
        :current-user-id="currentUserId"
        @delete-event="handleDeleteEvent"
        @load-more="handleLoadMore"
        @report-event="openReport"
        @block-user="openBlock"
      />

      <!-- Message Input: only for a club playing, until full time (SB-1330) -->
      <MessageInput
        v-if="canChat"
        ref="messageInput"
        @send="handleSendMessage"
        :disabled="isSending"
        :error="sendError"
      />
      <p
        v-else-if="chatNote"
        class="chat-note"
        role="status"
        data-testid="chat-note"
      >
        {{ chatNote }}
      </p>

      <ChatSafetyDialog
        :mode="dialogMode"
        :username="dialogEvent?.created_by_username || ''"
        :busy="dialogBusy"
        @close="closeDialog"
        @report="handleReport"
        @block="handleBlock"
        @agree="handleAgreeRules"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useLiveMatch } from '../../composables/useLiveMatch';
import LiveScoreboard from './LiveScoreboard.vue';
import LiveAdminControls from './LiveAdminControls.vue';
import ActivityStream from './ActivityStream.vue';
import MessageInput from './MessageInput.vue';
import ChatSafetyDialog from './ChatSafetyDialog.vue';
import { useAuthStore } from '../../stores/auth';
import { useBlockedUsers } from '../../composables/useBlockedUsers';
import {
  CHAT_CLOSED,
  NOT_A_MEMBER,
  chatPostErrorMessage,
  chatRulesKey,
  visibleEvents,
} from '../../utils/chatSafety';

const props = defineProps({
  matchId: {
    type: Number,
    required: true,
  },
});

defineEmits(['back']);

const {
  matchState,
  events,
  isLoading,
  error,
  isConnected,
  clockDisplayFormatted,
  isInStoppage,
  matchPeriod,
  canManage,
  updateClock,
  reopenMatch,
  postGoal,
  postCard,
  postMessage,
  deleteEvent,
  loadMoreEvents,
  fetchMatchState,
  fetchTeamRosters,
  // Lineup
  homeLineup,
  awayLineup,
  fetchLineups,
  saveLineup,
  chat,
  setChatRoom,
} = useLiveMatch(props.matchId);

const sportType = computed(() => matchState.value?.sport_type || 'soccer');

const isSending = ref(false);

// ── Chat safety (SB-1324) ──
const authStore = useAuthStore();
const blockedUsers = useBlockedUsers();

const currentUserId = computed(() =>
  authStore.state.user?.id ? String(authStore.state.user.id) : null
);

// Reads already leave blocked authors' chat out; this hides what arrives
// over realtime and what was on screen when someone was blocked. Chat only:
// goals and cards a blocked user recorded stay.
const shownEvents = computed(() =>
  visibleEvents(events.value, blockedUsers.blockedIds.value)
);

// Club chat rooms (SB-1330). Closed once the match is over: messages stay
// readable, nobody posts.
const chatClosed = computed(
  () => chat.value.closed || matchPeriod.value === 'Full Time'
);
const canChat = computed(() => chat.value.available && !chatClosed.value);
const chatNote = computed(() => {
  if (!currentUserId.value) return '';
  if (!chat.value.available) return NOT_A_MEMBER + '.';
  if (chatClosed.value) return CHAT_CLOSED + '.';
  return '';
});

async function handleSwitchRoom(clubId) {
  sendError.value = '';
  const result = await setChatRoom(clubId);
  if (!result.success) {
    sendError.value = result.error || 'Failed to switch chat room';
  }
}

const messageInput = ref(null);
const sendError = ref('');
const dialogMode = ref(null);
const dialogEvent = ref(null);
const dialogBusy = ref(false);
// A message held back while the chat rules prompt is open.
let pendingMessage = null;

function closeDialog() {
  dialogMode.value = null;
  dialogEvent.value = null;
  pendingMessage = null;
}

function openReport(event) {
  sendError.value = '';
  dialogEvent.value = event;
  dialogMode.value = 'report';
}

function openBlock(event) {
  sendError.value = '';
  dialogEvent.value = event;
  dialogMode.value = 'block';
}

async function handleReport(reason) {
  const event = dialogEvent.value;
  if (!event) return;
  dialogBusy.value = true;
  try {
    // The server blocks the author too; report() hides their chat at once.
    await blockedUsers.report(props.matchId, event.id, reason);
    dialogEvent.value = null;
    dialogMode.value = 'reported';
  } catch (err) {
    closeDialog();
    sendError.value = err.message || 'Failed to report message';
  } finally {
    dialogBusy.value = false;
  }
}

async function handleBlock() {
  const authorId = dialogEvent.value?.created_by;
  if (!authorId) return;
  dialogBusy.value = true;
  try {
    await blockedUsers.block(authorId);
    closeDialog();
  } catch (err) {
    closeDialog();
    sendError.value = err.message || 'Failed to block user';
  } finally {
    dialogBusy.value = false;
  }
}

function rulesAccepted() {
  if (!currentUserId.value) return true;
  try {
    return localStorage.getItem(chatRulesKey(currentUserId.value)) === '1';
  } catch {
    return false;
  }
}

function handleAgreeRules() {
  try {
    localStorage.setItem(chatRulesKey(currentUserId.value), '1');
  } catch {
    // Storage unavailable: they will be asked again next time.
  }
  const message = pendingMessage;
  closeDialog();
  if (message) handleSendMessage(message);
}

async function handleUpdateClock(action) {
  const result = await updateClock(action);
  if (!result.success) {
    alert(result.error || 'Failed to update clock');
  }
}

async function handleReopenMatch() {
  const result = await reopenMatch();
  if (!result.success) {
    alert(result.error || 'Failed to reopen match');
  }
}

async function handlePostGoal({
  teamId,
  playerName,
  message,
  playerId,
  assistPlayerId,
}) {
  const result = await postGoal(
    teamId,
    playerName,
    message,
    playerId,
    assistPlayerId
  );
  if (!result.success) {
    alert(result.error || 'Failed to post goal');
  }
}

async function handlePostCard({
  teamId,
  playerId,
  playerName,
  cardType,
  message,
}) {
  const result = await postCard(
    teamId,
    playerId,
    cardType,
    message,
    playerName
  );
  if (!result.success) {
    alert(result.error || 'Failed to record card');
  }
}

async function handleSendMessage(message) {
  if (!message.trim()) return;

  if (!rulesAccepted()) {
    pendingMessage = message;
    dialogMode.value = 'rules';
    return;
  }

  isSending.value = true;
  sendError.value = '';
  try {
    const result = await postMessage(message);
    if (result.success) {
      messageInput.value?.clear();
    } else {
      sendError.value = chatPostErrorMessage(result.status, result.error);
    }
  } finally {
    isSending.value = false;
  }
}

async function handleDeleteEvent(eventId) {
  if (
    !confirm('Delete this event? If this is a goal, the score will be updated.')
  )
    return;

  const result = await deleteEvent(eventId);
  if (!result.success) {
    alert(result.error || 'Failed to delete event');
  }
}

async function handleLoadMore() {
  if (events.value.length === 0) return;
  const lastEvent = events.value[events.value.length - 1];
  await loadMoreEvents(lastEvent.id);
}
</script>

<style scoped>
/* Club chat rooms (SB-1330) */
.room-switcher {
  display: flex;
  gap: 8px;
  padding: 8px 16px 0;
}

.room-tab {
  flex: 1;
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid #333;
  border-radius: 8px;
  background: #16213e;
  color: #aaa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.room-tab.active {
  border-color: #2196f3;
  color: white;
}

.chat-note {
  margin: 0;
  padding: 16px;
  text-align: center;
  font-size: 14px;
  color: #888;
}

.live-match-view {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #1a1a2e;
  color: white;
}

/* Header */
.live-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #16213e;
  position: sticky;
  top: 0;
  z-index: 100;
}

.back-button {
  background: none;
  border: none;
  color: white;
  font-size: 24px;
  cursor: pointer;
  padding: 8px;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  text-align: center;
}

.live-badge {
  background: #e94560;
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.connection-status {
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #666;
}

.connection-status.connected .status-dot {
  background: #4caf50;
}

/* Loading */
.loading-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #333;
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Error */
.error-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px;
}

.error-message {
  color: #e94560;
  text-align: center;
}

.retry-button {
  background: #e94560;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  min-height: 44px;
}

/* Content */
.live-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding-bottom: 80px; /* Space for fixed message input */
}

/* Screen reader only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* Responsive */
@media (min-width: 640px) {
  .live-content {
    max-width: 640px;
    margin: 0 auto;
    width: 100%;
  }
}

@media (min-width: 1024px) {
  .live-content {
    max-width: 800px;
  }
}
</style>
