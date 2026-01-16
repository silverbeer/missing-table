<template>
  <div class="activity-stream">
    <div v-if="events.length === 0" class="empty-state">
      <p>No activity yet</p>
    </div>

    <div v-else class="events-list">
      <div
        v-for="event in events"
        :key="event.id"
        :class="['event', `event-${event.event_type}`]"
      >
        <!-- Goal Event -->
        <template v-if="event.event_type === 'goal'">
          <div class="event-icon goal-icon">
            <span>&#9917;</span>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span v-if="event.match_minute" class="match-minute">
                {{ formatMatchMinute(event) }}
              </span>
              <span class="event-time">{{ formatTime(event.created_at) }}</span>
              <span
                :class="[
                  'team-badge',
                  event.team_id === homeTeamId ? 'home' : 'away',
                ]"
              >
                {{ event.team_id === homeTeamId ? 'HOME' : 'AWAY' }}
              </span>
            </div>
            <div class="goal-scorer">{{ event.player_name }}</div>
            <div v-if="event.message" class="event-message">
              {{ event.message }}
            </div>
          </div>
          <button
            v-if="canDelete"
            @click="$emit('delete-event', event.id)"
            class="delete-button"
            title="Delete goal"
          >
            &#10005;
          </button>
        </template>

        <!-- Status Change Event -->
        <template v-else-if="event.event_type === 'status_change'">
          <div class="event-icon status-icon">
            <span>&#128337;</span>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span class="event-time">{{ formatTime(event.created_at) }}</span>
            </div>
            <div class="status-message">{{ event.message }}</div>
          </div>
        </template>

        <!-- Message Event -->
        <template v-else>
          <div class="event-icon message-icon">
            <span>&#128172;</span>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span class="username">{{
                event.created_by_username || 'Anonymous'
              }}</span>
              <span class="event-time">{{ formatTime(event.created_at) }}</span>
            </div>
            <div class="event-message">{{ event.message }}</div>
          </div>
          <button
            v-if="canDelete"
            @click="$emit('delete-event', event.id)"
            class="delete-button"
          >
            &#10005;
          </button>
        </template>
      </div>

      <!-- Load More -->
      <button
        v-if="events.length >= 20"
        @click="$emit('load-more')"
        class="load-more-button"
      >
        Load more...
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  events: {
    type: Array,
    default: () => [],
  },
  canDelete: {
    type: Boolean,
    default: false,
  },
  homeTeamId: {
    type: Number,
    required: true,
  },
});

defineEmits(['delete-event', 'load-more']);

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatMatchMinute(event) {
  if (!event.match_minute) return '';
  if (event.extra_time) {
    return `${event.match_minute}+${event.extra_time}'`;
  }
  return `${event.match_minute}'`;
}
</script>

<style scoped>
.activity-stream {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #666;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.event {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background: #16213e;
}

/* Goal events */
.event-goal {
  background: linear-gradient(135deg, #1b4332 0%, #16213e 100%);
  border-left: 3px solid #4caf50;
}

/* Status change events */
.event-status_change {
  background: #1e1e3f;
  border-left: 3px solid #ffc107;
}

/* Message events */
.event-message {
  background: #1a1a2e;
}

/* Event icons */
.event-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.goal-icon {
  background: #4caf50;
}

.status-icon {
  background: #ffc107;
  color: black;
}

.message-icon {
  background: #444;
}

/* Event content */
.event-content {
  flex: 1;
  min-width: 0;
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.username {
  font-weight: 600;
  color: #aaa;
  font-size: 14px;
}

.event-time {
  font-size: 12px;
  color: #666;
}

.match-minute {
  font-size: 14px;
  font-weight: bold;
  color: #4caf50;
  margin-right: 4px;
}

.team-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: bold;
}

.team-badge.home {
  background: #2196f3;
  color: white;
}

.team-badge.away {
  background: #f44336;
  color: white;
}

.goal-scorer {
  font-size: 16px;
  font-weight: bold;
  color: white;
  margin-bottom: 4px;
}

.status-message {
  font-size: 14px;
  font-weight: 600;
  color: #ffc107;
}

.event-message {
  font-size: 14px;
  color: #e0e0e0;
  word-break: break-word;
}

/* Delete button */
.delete-button {
  background: none;
  border: none;
  color: #666;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  opacity: 0.5;
  transition: opacity 0.2s;
  min-width: 32px;
  min-height: 32px;
}

.delete-button:hover {
  opacity: 1;
  color: #f44336;
}

/* Load more */
.load-more-button {
  width: 100%;
  padding: 12px;
  background: transparent;
  border: 1px solid #444;
  border-radius: 8px;
  color: #aaa;
  cursor: pointer;
  margin-top: 8px;
}

.load-more-button:hover {
  background: #1e1e3f;
}
</style>
