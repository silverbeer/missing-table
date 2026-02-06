<template>
  <div class="formation-field">
    <svg
      viewBox="0 0 100 120"
      class="field-svg"
      preserveAspectRatio="xMidYMid meet"
    >
      <!-- Soccer field -->
      <template v-if="sportType !== 'futsal'">
        <!-- Field background -->
        <rect x="0" y="0" width="100" height="120" class="field-bg soccer-bg" />

        <!-- Center circle -->
        <circle cx="50" cy="60" r="12" class="field-line" fill="none" />
        <circle cx="50" cy="60" r="1" class="field-line" />

        <!-- Center line -->
        <line x1="0" y1="60" x2="100" y2="60" class="field-line" />

        <!-- Goal boxes (top) -->
        <rect
          x="30"
          y="0"
          width="40"
          height="18"
          class="field-line"
          fill="none"
        />
        <rect
          x="38"
          y="0"
          width="24"
          height="8"
          class="field-line"
          fill="none"
        />

        <!-- Goal boxes (bottom) -->
        <rect
          x="30"
          y="102"
          width="40"
          height="18"
          class="field-line"
          fill="none"
        />
        <rect
          x="38"
          y="112"
          width="24"
          height="8"
          class="field-line"
          fill="none"
        />

        <!-- Penalty spots -->
        <circle cx="50" cy="14" r="0.8" class="field-line" />
        <circle cx="50" cy="106" r="0.8" class="field-line" />
      </template>

      <!-- Futsal court -->
      <template v-else>
        <!-- Court background -->
        <rect x="0" y="0" width="100" height="120" class="field-bg futsal-bg" />

        <!-- Court boundary -->
        <rect
          x="4"
          y="4"
          width="92"
          height="112"
          class="field-line"
          fill="none"
          rx="2"
        />

        <!-- Center line -->
        <line x1="4" y1="60" x2="96" y2="60" class="field-line" />

        <!-- Center circle -->
        <circle cx="50" cy="60" r="8" class="field-line" fill="none" />
        <circle cx="50" cy="60" r="1" class="field-line" />

        <!-- Penalty arcs (top) -->
        <path d="M 35 4 A 15 15 0 0 1 65 4" class="field-line" fill="none" />

        <!-- Penalty arcs (bottom) -->
        <path
          d="M 35 116 A 15 15 0 0 0 65 116"
          class="field-line"
          fill="none"
        />

        <!-- Penalty spots -->
        <circle cx="50" cy="18" r="0.8" class="field-line" />
        <circle cx="50" cy="102" r="0.8" class="field-line" />

        <!-- Goal areas (small rectangles) -->
        <rect
          x="38"
          y="4"
          width="24"
          height="6"
          class="field-line"
          fill="none"
        />
        <rect
          x="38"
          y="110"
          width="24"
          height="6"
          class="field-line"
          fill="none"
        />

        <!-- Corner arcs -->
        <path d="M 4 7 A 3 3 0 0 1 7 4" class="field-line" fill="none" />
        <path d="M 93 4 A 3 3 0 0 1 96 7" class="field-line" fill="none" />
        <path d="M 4 113 A 3 3 0 0 0 7 116" class="field-line" fill="none" />
        <path d="M 93 116 A 3 3 0 0 0 96 113" class="field-line" fill="none" />
      </template>

      <!-- Position markers -->
      <g
        v-for="pos in formationPositions"
        :key="pos.position"
        class="position-marker"
        :class="{
          assigned: getAssignment(pos.position),
          clickable: !readonly,
        }"
        :transform="`translate(${pos.x}, ${scaleY(pos.y)})`"
        @click="handlePositionClick(pos.position)"
      >
        <!-- Marker circle -->
        <circle
          r="5"
          :class="['marker-circle', { assigned: getAssignment(pos.position) }]"
        />

        <!-- Jersey number or position code -->
        <text
          class="marker-text"
          text-anchor="middle"
          dominant-baseline="central"
          font-size="4"
        >
          {{ getMarkerLabel(pos.position) }}
        </text>

        <!-- Player name below marker -->
        <text
          v-if="getAssignment(pos.position)"
          class="player-name"
          text-anchor="middle"
          y="9"
          font-size="3"
        >
          {{ getPlayerDisplayName(pos.position) }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { getFormations } from '../../config/formations';

const props = defineProps({
  formation: {
    type: String,
    required: true,
  },
  assignments: {
    type: Array,
    default: () => [],
  },
  roster: {
    type: Array,
    default: () => [],
  },
  readonly: {
    type: Boolean,
    default: false,
  },
  sportType: {
    type: String,
    default: 'soccer',
  },
});

const emit = defineEmits(['position-clicked']);

// Get positions for the current formation
const formationPositions = computed(() => {
  const formations = getFormations(props.sportType);
  const formationData = formations[props.formation];
  return formationData ? formationData.positions : [];
});

// Scale Y coordinate to fit the SVG viewBox (0-100 -> 10-110 to add padding)
function scaleY(y) {
  return 10 + (y * 100) / 100;
}

// Get the assignment for a position
function getAssignment(positionCode) {
  return props.assignments.find(a => a.position === positionCode);
}

// Get the label to show on the marker
function getMarkerLabel(positionCode) {
  const assignment = getAssignment(positionCode);
  if (assignment) {
    return assignment.jersey_number || '#';
  }
  return positionCode;
}

// Get the player display name for a position
function getPlayerDisplayName(positionCode) {
  const assignment = getAssignment(positionCode);
  if (!assignment) return '';

  // If we have a display_name from the assignment, use it
  if (assignment.display_name) {
    // Truncate long names
    const name = assignment.display_name;
    return name.length > 12 ? name.substring(0, 10) + '...' : name;
  }

  // Otherwise try to find in roster
  const player = props.roster.find(p => p.id === assignment.player_id);
  if (player) {
    const name =
      player.display_name ||
      `${player.first_name || ''} ${player.last_name || ''}`.trim();
    return name.length > 12 ? name.substring(0, 10) + '...' : name;
  }

  return '';
}

function handlePositionClick(positionCode) {
  if (!props.readonly) {
    emit('position-clicked', positionCode);
  }
}
</script>

<style scoped>
.formation-field {
  width: 100%;
  max-width: 300px;
  margin: 0 auto;
}

.field-svg {
  width: 100%;
  height: auto;
  display: block;
}

.field-bg.soccer-bg {
  fill: #2e7d32;
}

.field-bg.futsal-bg {
  fill: #2962a8;
}

.field-line {
  stroke: rgba(255, 255, 255, 0.5);
  stroke-width: 0.5;
  fill: rgba(255, 255, 255, 0.5);
}

.position-marker {
  cursor: default;
}

.position-marker.clickable {
  cursor: pointer;
}

.position-marker.clickable:hover .marker-circle {
  stroke: #ffc107;
  stroke-width: 1;
}

.marker-circle {
  fill: rgba(255, 255, 255, 0.3);
  stroke: rgba(255, 255, 255, 0.6);
  stroke-width: 0.5;
  transition: all 0.2s;
}

.marker-circle.assigned {
  fill: #2196f3;
  stroke: white;
  stroke-width: 0.8;
}

.marker-text {
  fill: white;
  font-weight: bold;
  pointer-events: none;
}

.player-name {
  fill: white;
  font-size: 3px;
  pointer-events: none;
}
</style>
