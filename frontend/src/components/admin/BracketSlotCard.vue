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

    <!-- Date/Time display (view mode) -->
    <div
      v-if="bracketSlot.match_id && !editing"
      class="mt-1 flex items-center justify-between text-xs text-gray-500"
    >
      <span>
        {{ displayDate }}
        <span v-if="displayTime" class="ml-1">{{ displayTime }}</span>
      </span>
      <button
        @click="startEditing"
        class="ml-2 text-gray-400 hover:text-blue-600"
        title="Edit date/time"
      >
        &#9998;
      </button>
    </div>

    <!-- Date/Time inline edit mode -->
    <div v-if="editing" class="mt-2 space-y-2">
      <div class="flex space-x-2">
        <input
          type="date"
          v-model="editDate"
          class="flex-1 text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <input
          type="time"
          v-model="editTime"
          class="flex-1 text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>
      <div class="flex justify-end space-x-2">
        <button
          @click="cancelEditing"
          class="text-xs px-2 py-1 text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          @click="saveDateTime"
          :disabled="saving"
          class="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>
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
import { ref, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'BracketSlotCard',
  props: {
    bracketSlot: { type: Object, required: true },
    actionLoading: { type: Boolean, default: false },
  },
  emits: ['advance', 'updated'],
  setup(props, { emit }) {
    const authStore = useAuthStore();

    const editing = ref(false);
    const saving = ref(false);
    const editDate = ref('');
    const editTime = ref('');

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

    // --- Date/Time display helpers ---

    const displayDate = computed(() => {
      const d = props.bracketSlot.match_date;
      if (!d) return '';
      return d;
    });

    const displayTime = computed(() => {
      return formatLocalTime(props.bracketSlot.scheduled_kickoff);
    });

    const formatLocalTime = isoString => {
      if (!isoString) return null;
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    };

    const extractLocalTime = isoString => {
      if (!isoString) return '';
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    };

    const toScheduledKickoffUTC = (dateStr, time) => {
      if (!dateStr || !time) return null;
      const localDateTime = new Date(`${dateStr}T${time}`);
      return localDateTime.toISOString();
    };

    // --- Edit mode ---

    const startEditing = () => {
      editDate.value = props.bracketSlot.match_date || '';
      editTime.value = extractLocalTime(props.bracketSlot.scheduled_kickoff);
      editing.value = true;
    };

    const cancelEditing = () => {
      editing.value = false;
    };

    const saveDateTime = async () => {
      if (!props.bracketSlot.match_id) return;

      try {
        saving.value = true;

        const body = {};
        if (editDate.value) {
          body.match_date = editDate.value;
        }
        if (editDate.value && editTime.value) {
          body.scheduled_kickoff = toScheduledKickoffUTC(
            editDate.value,
            editTime.value
          );
        }

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${props.bracketSlot.match_id}`,
          {
            method: 'PATCH',
            body: JSON.stringify(body),
          }
        );

        editing.value = false;
        emit('updated');
      } catch (err) {
        console.error('Failed to update match date/time:', err);
      } finally {
        saving.value = false;
      }
    };

    return {
      editing,
      saving,
      editDate,
      editTime,
      isCompleted,
      isHomeWinner,
      isAwayWinner,
      canAdvance,
      statusLabel,
      statusClass,
      displayDate,
      displayTime,
      startEditing,
      cancelEditing,
      saveDateTime,
    };
  },
};
</script>
