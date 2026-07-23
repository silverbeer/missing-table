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
      :warn-positions="outOfPositionSlots"
      @position-clicked="openPlayerSelector"
    />

    <!-- Unassigned players (bench) -->
    <div class="bench-section">
      <h4 class="bench-title">Bench ({{ unassignedPlayers.length }})</h4>
      <!-- SB-68: distinguish "no roster set up for this age group" from
           "every roster player is on the pitch". When the roster array is
           empty, surface a helpful pointer; when it's just fully assigned,
           keep the original message. -->
      <div
        v-if="roster.length === 0"
        class="no-bench no-roster"
        data-testid="lineup-empty-no-roster"
      >
        <p class="no-bench-headline">
          No roster set
          <template v-if="ageGroupName"> for {{ ageGroupName }}</template>
          <template v-if="teamName"> on {{ teamName }} </template>
        </p>
        <p class="no-bench-hint">
          Live-scoring still works — use "Other player" when recording events,
          or set up the roster via Profile → My Club.
        </p>
      </div>
      <div v-else-if="unassignedPlayers.length === 0" class="no-bench">
        All players assigned
      </div>
      <!-- SB-288+: bench grouped by position category with position chips -->
      <div v-else class="bench-groups">
        <div v-for="group in benchGroups" :key="group.key" class="bench-group">
          <div class="bench-group-label">{{ group.label }}</div>
          <div class="bench-list">
            <div
              v-for="player in group.players"
              :key="player.id"
              class="bench-player"
            >
              #{{ player.jersey_number }} {{ player.display_name }}
              <span
                v-if="parsePositions(player.positions).length"
                class="bench-positions"
                >{{ parsePositions(player.positions).join(' ') }}</span
              >
            </div>
          </div>
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
        @click="autoSuggestXI"
        :disabled="roster.length === 0 || openSlotCount === 0 || saving"
        class="suggest-button"
        title="Fill open slots with best-fit players"
      >
        Auto-fill
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

          <!-- Suggested: players whose position group matches the slot -->
          <template v-if="slotGroup && suggestedPlayers.length > 0">
            <div class="player-section-label">{{ groupNames[slotGroup] }}s</div>
            <button
              v-for="player in suggestedPlayers"
              :key="player.id"
              @click="assignPlayer(player.id, selectedPosition)"
              class="player-option suggested"
            >
              #{{ player.jersey_number }} {{ player.display_name }}
              <span class="player-positions">{{
                parsePositions(player.positions).join(' ')
              }}</span>
            </button>
          </template>

          <!-- Everyone else (incl. players with no positions set) -->
          <template v-if="otherPlayers.length > 0">
            <div
              v-if="slotGroup && suggestedPlayers.length > 0"
              class="player-section-label"
            >
              Other players
            </div>
            <button
              v-for="player in otherPlayers"
              :key="player.id"
              @click="assignPlayer(player.id, selectedPosition)"
              class="player-option"
            >
              #{{ player.jersey_number }} {{ player.display_name }}
              <span
                v-if="parsePositions(player.positions).length"
                class="player-positions"
                >{{ parsePositions(player.positions).join(' ') }}</span
              >
            </button>
          </template>

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
import {
  SLOT_TO_GROUP,
  GROUP_NAMES,
  groupForPosition,
  primaryPosition,
  parsePositions,
} from '@/constants/positions';

const groupNames = GROUP_NAMES;

const props = defineProps({
  teamId: {
    type: Number,
    required: true,
  },
  teamName: {
    type: String,
    default: '',
  },
  // SB-68: rendered in the "No roster set" empty-state so admins
  // immediately see which age group's roster is missing rather than just
  // an empty list.
  ageGroupName: {
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

// SB-288: partition modal candidates by position-group fit for the clicked
// slot. Soft partition, not a hard filter - quick-added rosters often have
// empty positions and must stay selectable.
const slotGroup = computed(() =>
  selectedPosition.value ? SLOT_TO_GROUP[selectedPosition.value] || null : null
);

const suggestedPlayers = computed(() => {
  if (!slotGroup.value) return [];
  return availablePlayersForModal.value
    .filter(p =>
      parsePositions(p.positions).some(
        code => groupForPosition(code) === slotGroup.value
      )
    )
    .sort((a, b) => {
      // Primary-position match first, then jersey number
      const aPrimary =
        groupForPosition(primaryPosition(parsePositions(a.positions))) ===
        slotGroup.value
          ? 0
          : 1;
      const bPrimary =
        groupForPosition(primaryPosition(parsePositions(b.positions))) ===
        slotGroup.value
          ? 0
          : 1;
      return aPrimary - bPrimary || a.jersey_number - b.jersey_number;
    });
});

const otherPlayers = computed(() => {
  if (!slotGroup.value) return availablePlayersForModal.value;
  const suggestedIds = new Set(suggestedPlayers.value.map(p => p.id));
  return availablePlayersForModal.value.filter(p => !suggestedIds.has(p.id));
});

// Position-group ordering used by the bench and auto-fill.
const GROUP_ORDER = ['GK', 'DEF', 'MID', 'FWD'];

// SB-288+: unassigned bench players grouped by their PRIMARY position group,
// GK -> DEF -> MID -> FWD, with an "Unassigned" bucket for players who have no
// positions set (quick-added rosters).
const benchGroups = computed(() => {
  const buckets = new Map();
  for (const player of unassignedPlayers.value) {
    const group = groupForPosition(
      primaryPosition(parsePositions(player.positions))
    );
    const key = group || 'NONE';
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(player);
  }
  const result = [];
  for (const key of GROUP_ORDER) {
    if (buckets.has(key)) {
      result.push({
        key,
        label: `${GROUP_NAMES[key]}s`,
        players: buckets.get(key),
      });
    }
  }
  if (buckets.has('NONE')) {
    result.push({
      key: 'NONE',
      label: 'No position set',
      players: buckets.get('NONE'),
    });
  }
  return result;
});

// SB-288+: formation slots whose assigned player is out of position (their
// position group doesn't include the slot's group). Players with no positions
// set are never flagged. Consumed by FormationField's amber marker.
const outOfPositionSlots = computed(() => {
  const slots = [];
  for (const assign of assignments.value) {
    const group = SLOT_TO_GROUP[assign.position];
    if (!group) continue;
    const player = props.roster.find(p => p.id === assign.player_id);
    const codes = parsePositions(player?.positions);
    if (codes.length === 0) continue;
    if (!codes.some(code => groupForPosition(code) === group)) {
      slots.push(assign.position);
    }
  }
  return slots;
});

// Number of empty slots in the current formation (drives Auto-fill enablement).
const openSlotCount = computed(() => {
  const formations = getFormations(props.sportType);
  const formation = formations[selectedFormation.value];
  if (!formation) return 0;
  const filled = new Set(assignments.value.map(a => a.position));
  return formation.positions.filter(p => !filled.has(p.position)).length;
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

// Fit score of a player for a slot group: 2 = primary in group,
// 1 = secondary position in group, 0 = no match / unknown.
function fitScore(player, group) {
  if (!group) return 0;
  const codes = parsePositions(player.positions);
  if (codes.length === 0) return 0;
  if (groupForPosition(primaryPosition(codes)) === group) return 2;
  if (codes.some(code => groupForPosition(code) === group)) return 1;
  return 0;
}

// SB-288+: one-tap "Auto-fill" — assign best-fit unassigned players to every
// OPEN slot (existing assignments are kept). Slots are filled GK->DEF->MID->FWD
// (formation order), each taking the highest-fit remaining player; ties break
// on jersey number. Non-matching fills still happen so the XI completes, but
// they surface via the out-of-position marker for the user to fix.
function autoSuggestXI() {
  const formations = getFormations(props.sportType);
  const formation = formations[selectedFormation.value];
  if (!formation) return;

  const filled = new Set(assignments.value.map(a => a.position));
  let pool = unassignedPlayers.value.slice();

  for (const slot of formation.positions) {
    if (filled.has(slot.position)) continue;
    if (pool.length === 0) break;

    const group = SLOT_TO_GROUP[slot.position] || null;
    let best = pool[0];
    let bestScore = fitScore(best, group);
    for (const player of pool) {
      const score = fitScore(player, group);
      if (
        score > bestScore ||
        (score === bestScore &&
          (player.jersey_number || 999) < (best.jersey_number || 999))
      ) {
        best = player;
        bestScore = score;
      }
    }

    assignments.value.push({
      player_id: best.id,
      position: slot.position,
      jersey_number: best.jersey_number,
      display_name:
        best.display_name ||
        `${best.first_name || ''} ${best.last_name || ''}`.trim(),
    });
    pool = pool.filter(p => p.id !== best.id);
  }

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

/* SB-68: empty-roster pointer (no roster set up for this age group). */
.no-bench.no-roster {
  font-style: normal;
  color: #ccc;
  padding: 4px 0;
}

.no-bench-headline {
  margin: 0 0 6px 0;
  font-size: 14px;
  font-weight: 600;
  color: #fbbf24; /* amber, matches the stoppage badge palette */
}

.no-bench-hint {
  margin: 0;
  font-size: 12px;
  color: #aaa;
  line-height: 1.4;
}

.bench-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bench-group-label {
  color: #888;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
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

.bench-positions {
  margin-left: 6px;
  color: #888;
  font-size: 11px;
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

.suggest-button {
  background: #2196f3;
  color: white;
}

.suggest-button:disabled {
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

.player-option.suggested {
  border-color: #2e7d32;
}

.player-option.suggested:hover {
  border-color: #4caf50;
  background: rgba(76, 175, 80, 0.1);
}

.player-section-label {
  color: #888;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 4px;
}

.player-positions {
  float: right;
  color: #888;
  font-size: 12px;
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
