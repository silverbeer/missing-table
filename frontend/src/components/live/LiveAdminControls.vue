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
      @click.self="showGoalModal = false"
    >
      <div class="modal-content">
        <h3 class="modal-title">Record Goal</h3>

        <div class="form-group">
          <label>Team</label>
          <div class="team-selector">
            <button
              @click="goalTeamId = matchState.home_team_id"
              :class="[
                'team-button',
                { selected: goalTeamId === matchState.home_team_id },
              ]"
            >
              {{ matchState.home_team_name }}
            </button>
            <button
              @click="goalTeamId = matchState.away_team_id"
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
          <label for="player-name">Player Name</label>
          <input
            id="player-name"
            v-model="goalPlayerName"
            type="text"
            placeholder="Enter player name"
            class="text-input"
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
          <button @click="showGoalModal = false" class="cancel-button">
            Cancel
          </button>
          <button
            @click="submitGoal"
            :disabled="!goalTeamId || !goalPlayerName.trim()"
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
});

const emit = defineEmits(['update-clock', 'post-goal']);

const showGoalModal = ref(false);
const goalTeamId = ref(null);
const goalPlayerName = ref('');
const goalMessage = ref('');

const showStartModal = ref(false);

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

function startMatch() {
  emit('update-clock', {
    action: 'start_first_half',
    half_duration: selectedDuration.value,
  });
  showStartModal.value = false;
}

function submitGoal() {
  if (!goalTeamId.value || !goalPlayerName.value.trim()) return;

  emit('post-goal', {
    teamId: goalTeamId.value,
    playerName: goalPlayerName.value.trim(),
    message: goalMessage.value.trim() || null,
  });

  // Reset form
  showGoalModal.value = false;
  goalTeamId.value = null;
  goalPlayerName.value = '';
  goalMessage.value = '';
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
</style>
