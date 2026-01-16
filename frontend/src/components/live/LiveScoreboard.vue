<template>
  <div class="scoreboard">
    <!-- Team Names -->
    <div class="teams">
      <div class="team home">
        <span class="team-name">{{ matchState.home_team_name }}</span>
      </div>
      <div class="vs">vs</div>
      <div class="team away">
        <span class="team-name">{{ matchState.away_team_name }}</span>
      </div>
    </div>

    <!-- Score -->
    <div class="score-container">
      <span class="score home-score">{{ matchState.home_score ?? 0 }}</span>
      <span class="score-separator">-</span>
      <span class="score away-score">{{ matchState.away_score ?? 0 }}</span>
    </div>

    <!-- Goal Scorers -->
    <div v-if="homeGoals.length || awayGoals.length" class="scorers-container">
      <div class="scorers home-scorers">
        <div v-for="goal in homeGoals" :key="goal.id" class="scorer">
          {{ goal.player_name }} {{ formatMinute(goal) }}
        </div>
      </div>
      <div class="scorers-divider"></div>
      <div class="scorers away-scorers">
        <div v-for="goal in awayGoals" :key="goal.id" class="scorer">
          {{ goal.player_name }} {{ formatMinute(goal) }}
        </div>
      </div>
    </div>

    <!-- Clock -->
    <div class="clock-container">
      <div class="clock">{{ elapsedTime }}</div>
      <div class="period" :class="periodClass">{{ matchPeriod }}</div>
    </div>

    <!-- Match Info -->
    <div class="match-info">
      <span v-if="matchState.age_group_name">{{
        matchState.age_group_name
      }}</span>
      <span v-if="matchState.division_name" class="separator">|</span>
      <span v-if="matchState.division_name">{{
        matchState.division_name
      }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  matchState: {
    type: Object,
    required: true,
  },
  elapsedTime: {
    type: String,
    required: true,
  },
  matchPeriod: {
    type: String,
    required: true,
  },
  events: {
    type: Array,
    default: () => [],
  },
});

const periodClass = computed(() => {
  switch (props.matchPeriod) {
    case '1st Half':
    case '2nd Half':
      return 'active';
    case 'Halftime':
      return 'halftime';
    case 'Full Time':
      return 'ended';
    default:
      return '';
  }
});

// Filter goals by team, sorted by match minute
const homeGoals = computed(() => {
  return props.events
    .filter(
      e =>
        e.event_type === 'goal' && e.team_id === props.matchState.home_team_id
    )
    .sort((a, b) => (a.match_minute || 0) - (b.match_minute || 0));
});

const awayGoals = computed(() => {
  return props.events
    .filter(
      e =>
        e.event_type === 'goal' && e.team_id === props.matchState.away_team_id
    )
    .sort((a, b) => (a.match_minute || 0) - (b.match_minute || 0));
});

// Format minute display (e.g., "22'" or "90+5'")
function formatMinute(goal) {
  if (!goal.match_minute) return '';
  if (goal.extra_time) {
    return `${goal.match_minute}+${goal.extra_time}'`;
  }
  return `${goal.match_minute}'`;
}
</script>

<style scoped>
.scoreboard {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  padding: 24px 16px;
  text-align: center;
  border-bottom: 1px solid #333;
}

/* Teams */
.teams {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.team {
  flex: 1;
  max-width: 140px;
}

.team-name {
  font-size: 14px;
  font-weight: 600;
  color: #e0e0e0;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vs {
  color: #666;
  font-size: 12px;
}

/* Score */
.score-container {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.score {
  font-size: 56px;
  font-weight: bold;
  color: white;
  min-width: 60px;
}

.score-separator {
  font-size: 32px;
  color: #666;
}

/* Goal Scorers */
.scorers-container {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 0 8px;
}

.scorers {
  flex: 1;
  max-width: 140px;
}

.home-scorers {
  text-align: right;
}

.away-scorers {
  text-align: left;
}

.scorers-divider {
  width: 1px;
  background: #444;
  min-height: 16px;
}

.scorer {
  font-size: 11px;
  color: #aaa;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Clock */
.clock-container {
  margin-bottom: 12px;
}

.clock {
  font-size: 32px;
  font-weight: bold;
  color: #e94560;
  font-family: monospace;
}

.period {
  font-size: 14px;
  color: #888;
  margin-top: 4px;
}

.period.active {
  color: #4caf50;
}

.period.halftime {
  color: #ffc107;
}

.period.ended {
  color: #666;
}

/* Match Info */
.match-info {
  font-size: 12px;
  color: #666;
}

.match-info .separator {
  margin: 0 8px;
}

/* Responsive */
@media (min-width: 640px) {
  .team-name {
    font-size: 18px;
  }

  .score {
    font-size: 72px;
    min-width: 80px;
  }

  .clock {
    font-size: 40px;
  }
}
</style>
