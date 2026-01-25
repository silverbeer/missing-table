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
        :elapsed-time="elapsedTimeFormatted"
        :match-period="matchPeriod"
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
        @update-clock="handleUpdateClock"
        @post-goal="handlePostGoal"
      />

      <!-- Activity Stream -->
      <ActivityStream
        :events="events"
        :can-delete="canManage"
        :home-team-id="matchState.home_team_id"
        @delete-event="handleDeleteEvent"
        @load-more="handleLoadMore"
      />

      <!-- Message Input -->
      <MessageInput @send="handleSendMessage" :disabled="isSending" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useLiveMatch } from '../../composables/useLiveMatch';
import LiveScoreboard from './LiveScoreboard.vue';
import LiveAdminControls from './LiveAdminControls.vue';
import ActivityStream from './ActivityStream.vue';
import MessageInput from './MessageInput.vue';

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
  elapsedTimeFormatted,
  matchPeriod,
  canManage,
  updateClock,
  postGoal,
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
} = useLiveMatch(props.matchId);

const isSending = ref(false);

async function handleUpdateClock(action) {
  const result = await updateClock(action);
  if (!result.success) {
    alert(result.error || 'Failed to update clock');
  }
}

async function handlePostGoal({ teamId, playerName, message, playerId }) {
  const result = await postGoal(teamId, playerName, message, playerId);
  if (!result.success) {
    alert(result.error || 'Failed to post goal');
  }
}

async function handleSendMessage(message) {
  if (!message.trim()) return;

  isSending.value = true;
  try {
    const result = await postMessage(message);
    if (!result.success) {
      alert(result.error || 'Failed to send message');
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
