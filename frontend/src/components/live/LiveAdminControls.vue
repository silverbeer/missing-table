<template>
  <div class="admin-controls">
    <!-- Clock Controls -->
    <div class="clock-controls">
      <button
        v-if="matchPeriod === 'Not Started'"
        @click="showStartModal = true"
        class="control-button start"
      >
        Start Match
      </button>

      <button
        v-if="matchPeriod === '1st Half'"
        @click="$emit('update-clock', 'start_halftime')"
        class="control-button halftime"
      >
        Halftime
      </button>

      <button
        v-if="matchPeriod === 'Halftime'"
        @click="$emit('update-clock', 'start_second_half')"
        class="control-button start"
      >
        Start 2nd Half
      </button>

      <button
        v-if="matchPeriod === '2nd Half'"
        @click="$emit('update-clock', 'end_match')"
        class="control-button end"
      >
        End Match
      </button>
    </div>

    <!-- Goal Button - only when clock is running (1st or 2nd half) -->
    <div
      v-if="matchPeriod === '1st Half' || matchPeriod === '2nd Half'"
      class="goal-controls"
    >
      <button @click="showGoalModal = true" class="control-button goal">
        + Goal
      </button>
    </div>

    <!-- Goal Modal -->
    <div
      v-if="showGoalModal"
      class="modal-overlay"
      @click.self="closeGoalModal"
    >
      <div class="modal-content">
        <h3 class="modal-title">Record Goal</h3>

        <div class="form-group">
          <label>Team</label>
          <div class="team-selector">
            <button
              @click="selectTeam(matchState.home_team_id)"
              :class="[
                'team-button',
                { selected: goalTeamId === matchState.home_team_id },
              ]"
            >
              {{ matchState.home_team_name }}
            </button>
            <button
              @click="selectTeam(matchState.away_team_id)"
              :class="[
                'team-button',
                { selected: goalTeamId === matchState.away_team_id },
              ]"
            >
              {{ matchState.away_team_name }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label for="player-select">Goal Scorer</label>
          <div v-if="rostersLoading" class="roster-loading">
            Loading roster...
          </div>
          <select
            v-else-if="currentTeamRoster.length > 0"
            id="player-select"
            v-model="selectedPlayerId"
            class="player-select"
          >
            <option :value="null">Select player...</option>
            <option
              v-for="player in currentTeamRoster"
              :key="player.id"
              :value="player.id"
            >
              {{ formatPlayerOption(player) }}
            </option>
            <option value="other">Other (type name)</option>
          </select>
          <div v-else class="no-roster-message">No roster available</div>
          <!-- Fallback text input when "Other" is selected or no roster -->
          <input
            v-if="
              selectedPlayerId === 'other' || currentTeamRoster.length === 0
            "
            v-model="goalPlayerName"
            type="text"
            placeholder="Enter player name"
            class="text-input mt-2"
          />
        </div>

        <div class="form-group">
          <label for="goal-message">Description (optional)</label>
          <input
            id="goal-message"
            v-model="goalMessage"
            type="text"
            placeholder="e.g., Header from corner"
            class="text-input"
          />
        </div>

        <div class="modal-actions">
          <button @click="closeGoalModal" class="cancel-button">Cancel</button>
          <button
            @click="submitGoal"
            :disabled="!canSubmitGoal"
            class="submit-button"
          >
            Record Goal
          </button>
        </div>
      </div>
    </div>

    <!-- Start Match Modal -->
    <div
      v-if="showStartModal"
      class="modal-overlay"
      @click.self="showStartModal = false"
    >
      <div class="modal-content">
        <h3 class="modal-title">Start Match</h3>

        <div class="form-group">
          <label>Half Duration (minutes)</label>
          <div class="duration-presets">
            <button
              @click="selectedDuration = 35"
              :class="['preset-button', { selected: selectedDuration === 35 }]"
            >
              35 (U13)
            </button>
            <button
              @click="selectedDuration = 40"
              :class="['preset-button', { selected: selectedDuration === 40 }]"
            >
              40 (U14-15)
            </button>
            <button
              @click="selectedDuration = 45"
              :class="['preset-button', { selected: selectedDuration === 45 }]"
            >
              45 (U16+)
            </button>
          </div>
          <div class="duration-input-row">
            <input
              v-model.number="selectedDuration"
              type="number"
              min="20"
              max="60"
              class="duration-input"
            />
            <span class="duration-label"
              >min/half = {{ selectedDuration * 2 }} min total</span
            >
          </div>
        </div>

        <div class="modal-actions">
          <button @click="showStartModal = false" class="cancel-button">
            Cancel
          </button>
          <button
            @click="startMatch"
            :disabled="selectedDuration < 20 || selectedDuration > 60"
            class="submit-button"
          >
            Start Match
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  matchState: {
    type: Object,
    required: true,
  },
  matchPeriod: {
    type: String,
    required: true,
  },
  fetchRosters: {
    type: Function,
    default: null,
  },
});

const emit = defineEmits(['update-clock', 'post-goal']);

// Goal modal state
const showGoalModal = ref(false);
const goalTeamId = ref(null);
const goalPlayerName = ref('');
const goalMessage = ref('');
const selectedPlayerId = ref(null);

// Roster state
const homeRoster = ref([]);
const awayRoster = ref([]);
const rostersLoading = ref(false);
const rostersLoaded = ref(false);

// Start match modal state
const showStartModal = ref(false);

// Compute current team roster based on selected team
const currentTeamRoster = computed(() => {
  if (!goalTeamId.value) return [];
  if (goalTeamId.value === props.matchState.home_team_id) {
    return homeRoster.value;
  }
  return awayRoster.value;
});

// Compute whether goal can be submitted
const canSubmitGoal = computed(() => {
  if (!goalTeamId.value) return false;
  // If a player is selected from roster
  if (selectedPlayerId.value && selectedPlayerId.value !== 'other') return true;
  // If "Other" or no roster, need a player name
  if (goalPlayerName.value.trim()) return true;
  return false;
});

// Compute default duration based on age group
const defaultDuration = computed(() => {
  const ageGroup = props.matchState?.age_group_name?.toLowerCase() || '';
  if (ageGroup.includes('u13') || ageGroup.includes('u-13')) return 35;
  if (ageGroup.includes('u14') || ageGroup.includes('u-14')) return 40;
  if (ageGroup.includes('u15') || ageGroup.includes('u-15')) return 40;
  // U16, U17, U19 and default
  return 45;
});

const selectedDuration = ref(defaultDuration.value);

// Update selected duration when modal opens (in case age group wasn't loaded initially)
watch(showStartModal, newVal => {
  if (newVal) {
    selectedDuration.value = defaultDuration.value;
  }
});

// Load rosters when goal modal opens
watch(showGoalModal, async newVal => {
  if (newVal && props.fetchRosters && !rostersLoaded.value) {
    rostersLoading.value = true;
    try {
      const rosters = await props.fetchRosters();
      homeRoster.value = rosters.home || [];
      awayRoster.value = rosters.away || [];
      rostersLoaded.value = true;
    } catch (err) {
      console.error('Failed to load rosters:', err);
    } finally {
      rostersLoading.value = false;
    }
  }
});

// Handle team selection
function selectTeam(teamId) {
  goalTeamId.value = teamId;
  // Reset player selection when team changes
  selectedPlayerId.value = null;
  goalPlayerName.value = '';
}

// Close goal modal and reset state
function closeGoalModal() {
  showGoalModal.value = false;
  goalTeamId.value = null;
  selectedPlayerId.value = null;
  goalPlayerName.value = '';
  goalMessage.value = '';
}

function startMatch() {
  emit('update-clock', {
    action: 'start_first_half',
    half_duration: selectedDuration.value,
  });
  showStartModal.value = false;
}

// Format player option for dropdown - avoid showing "#33 #33" for unlinked players
function formatPlayerOption(player) {
  const jerseyNum = player.jersey_number;
  const displayName = player.display_name;

  // If display_name is empty, null, or just the jersey number (with or without #), show only jersey number
  if (
    !displayName ||
    displayName === `#${jerseyNum}` ||
    displayName === String(jerseyNum)
  ) {
    return `#${jerseyNum}`;
  }

  return `#${jerseyNum} ${displayName}`;
}

function submitGoal() {
  if (!canSubmitGoal.value) return;

  // Determine player info to send
  let playerId = null;
  let playerName = null;

  if (selectedPlayerId.value && selectedPlayerId.value !== 'other') {
    // Player selected from roster
    playerId = selectedPlayerId.value;
    // Find player name for display
    const player = currentTeamRoster.value.find(p => p.id === playerId);
    playerName = player?.display_name || `#${player?.jersey_number}`;
  } else {
    // Manual entry
    playerName = goalPlayerName.value.trim();
  }

  emit('post-goal', {
    teamId: goalTeamId.value,
    playerName,
    playerId,
    message: goalMessage.value.trim() || null,
  });

  closeGoalModal();
}
</script>

<style scoped>
.admin-controls {
  padding: 12px 16px;
  background: #1e1e3f;
  border-bottom: 1px solid #333;
}

.clock-controls,
.goal-controls {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.goal-controls {
  margin-top: 12px;
}

.control-button {
  flex: 1;
  max-width: 200px;
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  min-height: 48px;
  transition: background-color 0.2s;
}

.control-button.start {
  background: #4caf50;
  color: white;
}

.control-button.start:hover {
  background: #43a047;
}

.control-button.halftime {
  background: #ffc107;
  color: black;
}

.control-button.halftime:hover {
  background: #ffb300;
}

.control-button.end {
  background: #f44336;
  color: white;
}

.control-button.end:hover {
  background: #e53935;
}

.control-button.goal {
  background: #2196f3;
  color: white;
}

.control-button.goal:hover {
  background: #1e88e5;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 16px;
}

.modal-content {
  background: #1e1e3f;
  border-radius: 12px;
  padding: 24px;
  width: 100%;
  max-width: 400px;
}

.modal-title {
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 20px;
  text-align: center;
  color: white;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  color: #aaa;
  margin-bottom: 8px;
}

.team-selector {
  display: flex;
  gap: 8px;
}

.team-button {
  flex: 1;
  padding: 12px;
  border: 2px solid #444;
  border-radius: 8px;
  background: transparent;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 48px;
}

.team-button.selected {
  border-color: #2196f3;
  background: rgba(33, 150, 243, 0.2);
}

.duration-presets {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.preset-button {
  flex: 1;
  padding: 10px 8px;
  border: 2px solid #444;
  border-radius: 8px;
  background: transparent;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 44px;
}

.preset-button.selected {
  border-color: #4caf50;
  background: rgba(76, 175, 80, 0.2);
}

.preset-button:hover:not(.selected) {
  border-color: #666;
}

.duration-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.duration-input {
  width: 80px;
  padding: 12px;
  border: 2px solid #444;
  border-radius: 8px;
  background: #16213e;
  color: white;
  font-size: 18px;
  font-weight: bold;
  text-align: center;
  min-height: 48px;
}

.duration-input:focus {
  outline: none;
  border-color: #4caf50;
}

.duration-input::-webkit-inner-spin-button,
.duration-input::-webkit-outer-spin-button {
  opacity: 1;
}

.duration-label {
  color: #aaa;
  font-size: 14px;
}

.text-input {
  width: 100%;
  padding: 12px;
  border: 2px solid #444;
  border-radius: 8px;
  background: #16213e;
  color: white;
  font-size: 16px;
  min-height: 48px;
}

.text-input:focus {
  outline: none;
  border-color: #2196f3;
}

.modal-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.cancel-button,
.submit-button {
  flex: 1;
  padding: 14px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  min-height: 48px;
}

.cancel-button {
  background: #444;
  color: white;
}

.submit-button {
  background: #4caf50;
  color: white;
}

.submit-button:disabled {
  background: #666;
  cursor: not-allowed;
}

/* Player selection styles */
.player-select {
  width: 100%;
  padding: 12px;
  border: 2px solid #444;
  border-radius: 8px;
  background: #16213e;
  color: white;
  font-size: 16px;
  min-height: 48px;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23aaa' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
}

.player-select:focus {
  outline: none;
  border-color: #2196f3;
}

.player-select option {
  background: #16213e;
  color: white;
  padding: 8px;
}

.roster-loading {
  color: #aaa;
  font-size: 14px;
  padding: 12px;
  text-align: center;
}

.no-roster-message {
  color: #888;
  font-size: 14px;
  padding: 8px 0;
}

.mt-2 {
  margin-top: 8px;
}
</style>
