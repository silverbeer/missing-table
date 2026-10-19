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

        <!-- Card Event -->
        <template
          v-else-if="
            event.event_type === 'red_card' ||
            event.event_type === 'yellow_card'
          "
        >
          <div
            :class="[
              'event-icon card-icon',
              event.event_type === 'red_card' ? 'red-card' : 'yellow-card',
            ]"
          >
            <span class="card-rect"></span>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span v-if="event.match_minute" class="match-minute card-minute">
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
            <div class="card-player">{{ event.player_name }}</div>
            <div v-if="event.message" class="event-message">
              {{ event.message }}
            </div>
          </div>
          <button
            v-if="canDelete"
            @click="$emit('delete-event', event.id)"
            class="delete-button"
            title="Delete card"
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

        <!-- Substitution / Position Change Event (SB-1354) -->
        <template
          v-else-if="
            event.event_type === 'substitution' ||
            event.event_type === 'position_change'
          "
        >
          <div
            :class="[
              'event-icon',
              event.event_type === 'substitution'
                ? 'sub-icon'
                : 'position-icon',
            ]"
            data-testid="lineup-event-icon"
          >
            <span v-if="event.event_type === 'substitution'">&#8644;</span>
            <span v-else>&#8596;</span>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span
                v-if="event.match_minute"
                class="match-minute lineup-minute"
              >
                {{ formatMatchMinute(event) }}
              </span>
              <span class="event-time">{{ formatTime(event.created_at) }}</span>
              <span
                v-if="event.team_id"
                :class="[
                  'team-badge',
                  event.team_id === homeTeamId ? 'home' : 'away',
                ]"
              >
                {{ event.team_id === homeTeamId ? 'HOME' : 'AWAY' }}
              </span>
            </div>
            <div v-if="event.message" class="lineup-message">
              {{ event.message }}
            </div>
          </div>
          <button
            v-if="canDelete"
            @click="$emit('delete-event', event.id)"
            class="delete-button"
            data-testid="delete-event"
            :title="
              event.event_type === 'substitution'
                ? 'Delete substitution'
                : 'Delete position change'
            "
          >
            &#10005;
          </button>
        </template>

        <!-- Message Event -->
        <template v-else-if="event.event_type === 'message'">
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
            <!-- Report and Block on other people's chat; Delete on your own
                 (managers can still delete anyone's) — SB-1324. -->
            <div
              v-if="isOthers(event)"
              class="chat-actions"
              data-testid="chat-actions"
            >
              <button
                type="button"
                class="chat-action"
                data-testid="report-message"
                @click="$emit('report-event', event)"
              >
                Report
              </button>
              <button
                v-if="event.created_by"
                type="button"
                class="chat-action"
                data-testid="block-user"
                @click="$emit('block-user', event)"
              >
                Block
              </button>
            </div>
          </div>
          <button
            v-if="canDelete || isMine(event)"
            @click="$emit('delete-event', event.id)"
            class="delete-button"
            data-testid="delete-message"
            title="Delete message"
          >
            &#10005;
          </button>
        </template>

        <!-- Any other event type: neutral row, never chat actions -->
        <template v-else>
          <div class="event-icon other-icon">
            <span>&#8226;</span>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span v-if="event.match_minute" class="match-minute">
                {{ formatMatchMinute(event) }}
              </span>
              <span class="event-time">{{ formatTime(event.created_at) }}</span>
            </div>
            <div v-if="event.message" class="other-message">
              {{ event.message }}
            </div>
          </div>
          <button
            v-if="canDelete"
            @click="$emit('delete-event', event.id)"
            class="delete-button"
            data-testid="delete-event"
            title="Delete event"
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
const props = defineProps({
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
  // The signed-in user's id; null when signed out (no chat actions then).
  currentUserId: {
    type: String,
    default: null,
  },
});

defineEmits(['delete-event', 'load-more', 'report-event', 'block-user']);

function isMine(event) {
  return (
    !!props.currentUserId &&
    !!event.created_by &&
    String(event.created_by) === props.currentUserId
  );
}

function isOthers(event) {
  return !!props.currentUserId && !isMine(event);
}

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

/* Card events */
.event-red_card {
  background: linear-gradient(135deg, #4a1a1a 0%, #16213e 100%);
  border-left: 3px solid #d32f2f;
}

.event-yellow_card {
  background: linear-gradient(135deg, #4a3a0a 0%, #16213e 100%);
  border-left: 3px solid #f9a825;
}

/* Substitution / position change events (SB-1354) */
.event-substitution {
  background: linear-gradient(135deg, #0d3b4a 0%, #16213e 100%);
  border-left: 3px solid #26c6da;
}

.event-position_change {
  background: linear-gradient(135deg, #2e1f4a 0%, #16213e 100%);
  border-left: 3px solid #9575cd;
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

.sub-icon {
  background: #26c6da;
  color: #0d1b2a;
  font-weight: bold;
}

.position-icon {
  background: #9575cd;
  color: white;
  font-weight: bold;
}

.other-icon {
  background: #333;
  color: #aaa;
}

.lineup-minute {
  color: #26c6da;
}

.event-position_change .lineup-minute {
  color: #b39ddb;
}

.lineup-message {
  font-size: 14px;
  font-weight: 600;
  color: #e0e0e0;
  word-break: break-word;
}

.other-message {
  font-size: 14px;
  color: #bbb;
  word-break: break-word;
}

.card-icon {
  border-radius: 50%;
}

.card-icon.red-card {
  background: #d32f2f;
}

.card-icon.yellow-card {
  background: #f9a825;
}

.card-rect {
  display: inline-block;
  width: 12px;
  height: 16px;
  border-radius: 2px;
  background: white;
}

.card-minute {
  color: #ff9800;
}

.card-player {
  font-size: 16px;
  font-weight: bold;
  color: white;
  margin-bottom: 4px;
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

/* Chat safety actions */
.chat-actions {
  display: flex;
  gap: 12px;
  margin-top: 6px;
}

.chat-action {
  background: none;
  border: none;
  padding: 2px 0;
  font-size: 12px;
  color: #888;
  cursor: pointer;
}

.chat-action:hover {
  color: #f44336;
  text-decoration: underline;
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
