<template>
  <div
    class="border rounded-lg p-3 bg-white shadow-sm"
    :class="{
      'border-green-400': isCompleted,
      'border-gray-200': !isCompleted,
    }"
  >
    <!-- Home team -->
    <div
      class="flex justify-between items-center py-1"
      :class="{ 'font-bold text-green-700': isHomeWinner }"
    >
      <div class="flex items-center space-x-2">
        <span
          v-if="bracketSlot.home_seed"
          class="text-xs text-gray-400 w-4 text-right"
        >
          {{ bracketSlot.home_seed }}
        </span>
        <span class="text-sm">
          {{ bracketSlot.home_team_name || 'TBD' }}
        </span>
      </div>
      <span class="text-sm font-mono">
        {{ bracketSlot.home_score ?? '-' }}
      </span>
    </div>

    <hr class="border-gray-100" />

    <!-- Away team -->
    <div
      class="flex justify-between items-center py-1"
      :class="{ 'font-bold text-green-700': isAwayWinner }"
    >
      <div class="flex items-center space-x-2">
        <span
          v-if="bracketSlot.away_seed"
          class="text-xs text-gray-400 w-4 text-right"
        >
          {{ bracketSlot.away_seed }}
        </span>
        <span class="text-sm">
          {{ bracketSlot.away_team_name || 'TBD' }}
        </span>
      </div>
      <span class="text-sm font-mono">
        {{ bracketSlot.away_score ?? '-' }}
      </span>
    </div>

    <!-- Status & Actions -->
    <div class="mt-2 flex justify-between items-center">
      <span class="text-xs" :class="statusClass">
        {{ statusLabel }}
      </span>
      <button
        v-if="canAdvance"
        @click="$emit('advance', bracketSlot.id)"
        :disabled="actionLoading"
        class="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        Advance Winner
      </button>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'BracketSlotCard',
  props: {
    bracketSlot: { type: Object, required: true },
    actionLoading: { type: Boolean, default: false },
  },
  emits: ['advance'],
  setup(props) {
    const isCompleted = computed(
      () => props.bracketSlot.match_status === 'completed'
    );

    const isHomeWinner = computed(
      () =>
        isCompleted.value &&
        props.bracketSlot.home_score != null &&
        props.bracketSlot.away_score != null &&
        props.bracketSlot.home_score > props.bracketSlot.away_score
    );

    const isAwayWinner = computed(
      () =>
        isCompleted.value &&
        props.bracketSlot.home_score != null &&
        props.bracketSlot.away_score != null &&
        props.bracketSlot.away_score > props.bracketSlot.home_score
    );

    const canAdvance = computed(
      () =>
        isCompleted.value &&
        props.bracketSlot.home_score !== props.bracketSlot.away_score &&
        props.bracketSlot.round !== 'final'
    );

    const statusLabel = computed(() => {
      if (!props.bracketSlot.match_id) return 'Awaiting teams';
      if (props.bracketSlot.match_status === 'completed') return 'Completed';
      if (props.bracketSlot.match_status === 'live') return 'Live';
      return 'Scheduled';
    });

    const statusClass = computed(() => {
      if (!props.bracketSlot.match_id) return 'text-gray-400';
      if (props.bracketSlot.match_status === 'completed')
        return 'text-green-600';
      if (props.bracketSlot.match_status === 'live')
        return 'text-red-600 font-bold';
      return 'text-blue-600';
    });

    return {
      isCompleted,
      isHomeWinner,
      isAwayWinner,
      canAdvance,
      statusLabel,
      statusClass,
    };
  },
};
</script>
