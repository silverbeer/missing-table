<template>
  <div class="lineup-manager">
    <!-- Formation selector -->
    <div class="formation-selector">
      <label for="formation-select">Formation</label>
      <select
        id="formation-select"
        v-model="selectedFormation"
        class="formation-select"
        @change="handleFormationChange"
      >
        <option
          v-for="opt in formationOptions"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </option>
      </select>
    </div>

    <!-- Formation field display -->
    <FormationField
      :formation="selectedFormation"
      :assignments="assignments"
      :roster="roster"
      :sport-type="sportType"
      @position-clicked="openPlayerSelector"
    />

    <!-- Unassigned players (bench) -->
    <div class="bench-section">
      <h4 class="bench-title">Bench ({{ unassignedPlayers.length }})</h4>
      <div v-if="unassignedPlayers.length === 0" class="no-bench">
        All players assigned
      </div>
      <div v-else class="bench-list">
        <div
          v-for="player in unassignedPlayers"
          :key="player.id"
          class="bench-player"
        >
          #{{ player.jersey_number }} {{ player.display_name }}
        </div>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="lineup-actions">
      <button
        @click="handleClear"
        :disabled="assignments.length === 0 || saving"
        class="clear-button"
      >
        Clear All
      </button>
      <button
        @click="handleSave"
        :disabled="!hasChanges || saving"
        class="save-button"
      >
        {{ saving ? 'Saving...' : 'Save Lineup' }}
      </button>
    </div>

    <!-- Player selection modal -->
    <div
      v-if="showPlayerModal"
      class="modal-overlay"
      @click.self="closePlayerModal"
    >
      <div class="modal-content">
        <h3 class="modal-title">Select Player for {{ selectedPosition }}</h3>

        <div class="player-list">
          <!-- Option to clear position -->
          <button
            v-if="getAssignmentForPosition(selectedPosition)"
            @click="clearPosition(selectedPosition)"
            class="player-option clear-option"
          >
            Clear Position
          </button>

          <!-- Available players -->
          <button
            v-for="player in availablePlayersForModal"
            :key="player.id"
            @click="assignPlayer(player.id, selectedPosition)"
            class="player-option"
          >
            #{{ player.jersey_number }} {{ player.display_name }}
          </button>

          <div v-if="availablePlayersForModal.length === 0" class="no-players">
            No available players
          </div>
        </div>

        <div class="modal-actions">
          <button @click="closePlayerModal" class="cancel-button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import FormationField from './FormationField.vue';
import {
  getFormations,
  getDefaultFormation,
  getFormationOptions,
} from '../../config/formations';

const props = defineProps({
  teamId: {
    type: Number,
    required: true,
  },
  teamName: {
    type: String,
    default: '',
  },
  roster: {
    type: Array,
    default: () => [],
  },
  initialLineup: {
    type: Object,
    default: null,
  },
  saving: {
    type: Boolean,
    default: false,
  },
  sportType: {
    type: String,
    default: 'soccer',
  },
});

const emit = defineEmits(['save', 'change']);

// State
const selectedFormation = ref(getDefaultFormation(props.sportType));
const assignments = ref([]); // Array of { player_id, position, jersey_number, display_name }
const showPlayerModal = ref(false);
const selectedPosition = ref(null);
const originalLineup = ref(null);

// Formation options
const formationOptions = computed(() => getFormationOptions(props.sportType));

// Computed: players not assigned to any position
const unassignedPlayers = computed(() => {
  const assignedIds = new Set(assignments.value.map(a => a.player_id));
  return props.roster.filter(p => !assignedIds.has(p.id));
});

// Computed: players available for selection in modal (not already assigned elsewhere)
const availablePlayersForModal = computed(() => {
  if (!selectedPosition.value) return [];

  // Get all assigned player IDs except the one currently in this position
  const assignedIds = new Set(
    assignments.value
      .filter(a => a.position !== selectedPosition.value)
      .map(a => a.player_id)
  );

  // Available = not assigned elsewhere
  return props.roster.filter(p => !assignedIds.has(p.id));
});

// Computed: has the lineup changed from initial state?
const hasChanges = computed(() => {
  if (!originalLineup.value) {
    return assignments.value.length > 0;
  }

  // Compare formation
  if (selectedFormation.value !== originalLineup.value.formation_name) {
    return true;
  }

  // Compare assignments
  const origPositions = originalLineup.value.positions || [];
  if (assignments.value.length !== origPositions.length) {
    return true;
  }

  // Check each assignment
  for (const assign of assignments.value) {
    const orig = origPositions.find(p => p.position === assign.position);
    if (!orig || orig.player_id !== assign.player_id) {
      return true;
    }
  }

  return false;
});

// Get assignment for a specific position
function getAssignmentForPosition(positionCode) {
  return assignments.value.find(a => a.position === positionCode);
}

// Open player selection modal for a position
function openPlayerSelector(positionCode) {
  selectedPosition.value = positionCode;
  showPlayerModal.value = true;
}

// Close player modal
function closePlayerModal() {
  showPlayerModal.value = false;
  selectedPosition.value = null;
}

// Assign a player to a position
function assignPlayer(playerId, positionCode) {
  // Remove any existing assignment for this position
  assignments.value = assignments.value.filter(
    a => a.position !== positionCode
  );

  // Find player details
  const player = props.roster.find(p => p.id === playerId);
  if (player) {
    assignments.value.push({
      player_id: playerId,
      position: positionCode,
      jersey_number: player.jersey_number,
      display_name:
        player.display_name ||
        `${player.first_name || ''} ${player.last_name || ''}`.trim(),
    });
  }

  closePlayerModal();
  emitChange();
}

// Clear a position
function clearPosition(positionCode) {
  assignments.value = assignments.value.filter(
    a => a.position !== positionCode
  );
  closePlayerModal();
  emitChange();
}

// Handle formation change
function handleFormationChange() {
  // Clear assignments that don't exist in the new formation
  const formations = getFormations(props.sportType);
  const newFormation = formations[selectedFormation.value];
  if (newFormation) {
    const validPositions = new Set(newFormation.positions.map(p => p.position));
    assignments.value = assignments.value.filter(a =>
      validPositions.has(a.position)
    );
  }
  emitChange();
}

// Clear all assignments
function handleClear() {
  assignments.value = [];
  emitChange();
}

// Save lineup
function handleSave() {
  emit('save', {
    formation_name: selectedFormation.value,
    positions: assignments.value.map(a => ({
      player_id: a.player_id,
      position: a.position,
    })),
  });
}

// Emit change event
function emitChange() {
  emit('change', {
    formation_name: selectedFormation.value,
    positions: assignments.value,
  });
}

// Initialize from initial lineup
function initializeFromLineup(lineup) {
  if (lineup) {
    selectedFormation.value =
      lineup.formation_name || getDefaultFormation(props.sportType);

    // Map positions with player details
    const positions = lineup.positions || [];
    assignments.value = positions.map(p => {
      const player = props.roster.find(r => r.id === p.player_id);
      return {
        player_id: p.player_id,
        position: p.position,
        jersey_number: p.jersey_number || player?.jersey_number,
        display_name:
          p.display_name ||
          player?.display_name ||
          `${player?.first_name || ''} ${player?.last_name || ''}`.trim(),
      };
    });

    originalLineup.value = { ...lineup };
  } else {
    selectedFormation.value = getDefaultFormation(props.sportType);
    assignments.value = [];
    originalLineup.value = null;
  }
}

// Watch for initial lineup changes
watch(
  () => props.initialLineup,
  newLineup => {
    initializeFromLineup(newLineup);
  },
  { immediate: true }
);

// Re-initialize when roster changes (to update player details)
watch(
  () => props.roster,
  () => {
    if (props.initialLineup) {
      initializeFromLineup(props.initialLineup);
    }
  }
);
</script>

<style scoped>
.lineup-manager {
  padding: 16px;
}

.formation-selector {
  margin-bottom: 16px;
}

.formation-selector label {
  display: block;
  font-size: 14px;
  color: #aaa;
  margin-bottom: 8px;
}

.formation-select {
  width: 100%;
  padding: 12px;
  border: 2px solid #444;
  border-radius: 8px;
  background: #16213e;
  color: white;
  font-size: 16px;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23aaa' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
}

.formation-select:focus {
  outline: none;
  border-color: #2196f3;
}

.bench-section {
  margin-top: 20px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.bench-title {
  font-size: 14px;
  color: #aaa;
  margin: 0 0 8px 0;
}

.no-bench {
  color: #666;
  font-size: 13px;
  font-style: italic;
}

.bench-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bench-player {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  font-size: 13px;
  color: #ccc;
}

.lineup-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.clear-button,
.save-button {
  flex: 1;
  padding: 14px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  min-height: 48px;
}

.clear-button {
  background: #444;
  color: white;
}

.clear-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-button {
  background: #4caf50;
  color: white;
}

.save-button:disabled {
  background: #666;
  cursor: not-allowed;
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
  max-height: 80vh;
  overflow-y: auto;
}

.modal-title {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 16px;
  text-align: center;
  color: white;
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.player-option {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #444;
  border-radius: 8px;
  background: transparent;
  color: white;
  font-size: 15px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
}

.player-option:hover {
  border-color: #2196f3;
  background: rgba(33, 150, 243, 0.1);
}

.player-option.clear-option {
  border-color: #f44336;
  color: #f44336;
}

.player-option.clear-option:hover {
  background: rgba(244, 67, 54, 0.1);
}

.no-players {
  color: #888;
  text-align: center;
  padding: 20px;
}

.modal-actions {
  display: flex;
  justify-content: center;
}

.cancel-button {
  padding: 12px 32px;
  border: none;
  border-radius: 8px;
  background: #444;
  color: white;
  font-size: 16px;
  cursor: pointer;
}
</style>
