<template>
  <div class="space-y-4">
    <!-- Error display -->
    <div
      v-if="error"
      class="bg-red-900/30 border border-red-700 text-red-300 text-sm px-3 py-2 rounded"
    >
      {{ error }}
    </div>

    <!-- Read-only notice -->
    <div
      v-if="!canEdit"
      class="bg-slate-700/50 text-slate-400 text-xs px-3 py-2 rounded text-center"
    >
      View only - you can only edit stats for your own team.
    </div>

    <!-- Goals Section -->
    <div>
      <h4 class="text-slate-300 text-sm font-semibold mb-2">Goals</h4>

      <!-- Existing goals -->
      <div v-if="goalEvents.length" class="space-y-1 mb-2">
        <div
          v-for="event in goalEvents"
          :key="event.id"
          class="flex items-center justify-between bg-slate-700/50 px-3 py-1.5 rounded text-sm"
        >
          <span class="text-white">
            <span class="text-yellow-400 font-medium">{{
              formatMinute(event)
            }}</span>
            {{ event.player_name || 'Unknown' }}
          </span>
          <button
            v-if="canEdit"
            @click="$emit('remove-goal', event.id)"
            class="text-red-400 hover:text-red-300 text-xs px-1.5 py-0.5 rounded hover:bg-red-900/30"
          >
            Remove
          </button>
        </div>
      </div>
      <div v-else class="text-slate-500 text-xs mb-2">No goals recorded.</div>

      <!-- Add goal form -->
      <div v-if="canEdit" class="flex flex-wrap gap-2 items-end">
        <div class="flex-1 min-w-[120px]">
          <label class="text-slate-400 text-xs block mb-1">Player</label>
          <select
            v-model="goalForm.player_id"
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          >
            <option value="">Select player</option>
            <option v-for="p in roster" :key="p.id" :value="p.id">
              #{{ p.jersey_number }}
              {{
                p.display_name ||
                `${p.first_name || ''} ${p.last_name || ''}`.trim() ||
                `#${p.jersey_number}`
              }}
            </option>
          </select>
        </div>
        <div class="w-20">
          <label class="text-slate-400 text-xs block mb-1">Minute</label>
          <input
            v-model.number="goalForm.match_minute"
            type="number"
            min="1"
            max="130"
            placeholder="Min"
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          />
        </div>
        <div class="w-16">
          <label class="text-slate-400 text-xs block mb-1">+ET</label>
          <input
            v-model.number="goalForm.extra_time"
            type="number"
            min="1"
            placeholder=""
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          />
        </div>
        <button
          @click="submitGoal"
          :disabled="!goalForm.player_id || !goalForm.match_minute"
          class="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-slate-600 disabled:text-slate-400 text-white text-sm rounded font-medium transition-colors"
        >
          Add
        </button>
      </div>
    </div>

    <!-- Substitutions Section -->
    <div>
      <h4 class="text-slate-300 text-sm font-semibold mb-2">Substitutions</h4>

      <!-- Existing subs -->
      <div v-if="subEvents.length" class="space-y-1 mb-2">
        <div
          v-for="event in subEvents"
          :key="event.id"
          class="flex items-center justify-between bg-slate-700/50 px-3 py-1.5 rounded text-sm"
        >
          <span class="text-white">
            <span class="text-yellow-400 font-medium">{{
              formatMinute(event)
            }}</span>
            {{ event.message }}
          </span>
          <button
            v-if="canEdit"
            @click="$emit('remove-substitution', event.id)"
            class="text-red-400 hover:text-red-300 text-xs px-1.5 py-0.5 rounded hover:bg-red-900/30"
          >
            Remove
          </button>
        </div>
      </div>
      <div v-else class="text-slate-500 text-xs mb-2">
        No substitutions recorded.
      </div>

      <!-- Add substitution form -->
      <div v-if="canEdit" class="flex flex-wrap gap-2 items-end">
        <div class="flex-1 min-w-[120px]">
          <label class="text-slate-400 text-xs block mb-1">Player On</label>
          <select
            v-model="subForm.player_in_id"
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          >
            <option value="">Select player</option>
            <option v-for="p in roster" :key="p.id" :value="p.id">
              #{{ p.jersey_number }}
              {{
                p.display_name ||
                `${p.first_name || ''} ${p.last_name || ''}`.trim() ||
                `#${p.jersey_number}`
              }}
            </option>
          </select>
        </div>
        <div class="flex-1 min-w-[120px]">
          <label class="text-slate-400 text-xs block mb-1">Player Off</label>
          <select
            v-model="subForm.player_out_id"
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          >
            <option value="">Select player</option>
            <option v-for="p in roster" :key="p.id" :value="p.id">
              #{{ p.jersey_number }}
              {{
                p.display_name ||
                `${p.first_name || ''} ${p.last_name || ''}`.trim() ||
                `#${p.jersey_number}`
              }}
            </option>
          </select>
        </div>
        <div class="w-20">
          <label class="text-slate-400 text-xs block mb-1">Minute</label>
          <input
            v-model.number="subForm.match_minute"
            type="number"
            min="1"
            max="130"
            placeholder="Min"
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          />
        </div>
        <div class="w-16">
          <label class="text-slate-400 text-xs block mb-1">+ET</label>
          <input
            v-model.number="subForm.extra_time"
            type="number"
            min="1"
            placeholder=""
            class="w-full bg-slate-700 text-white text-sm rounded px-2 py-1.5 border border-slate-600"
          />
        </div>
        <button
          @click="submitSubstitution"
          :disabled="
            !subForm.player_in_id ||
            !subForm.player_out_id ||
            !subForm.match_minute
          "
          class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:text-slate-400 text-white text-sm rounded font-medium transition-colors"
        >
          Add
        </button>
      </div>
    </div>

    <!-- Player Stats Section -->
    <div>
      <h4 class="text-slate-300 text-sm font-semibold mb-2">Player Stats</h4>

      <div v-if="playerStats.length" class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-slate-400 text-xs border-b border-slate-700">
              <th class="text-left py-1.5 px-2">#</th>
              <th class="text-left py-1.5 px-2">Name</th>
              <th class="text-center py-1.5 px-2">Started</th>
              <th class="text-center py-1.5 px-2">Min</th>
              <th class="text-center py-1.5 px-2">Goals</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="player in editableStats"
              :key="player.player_id"
              class="border-b border-slate-700/50"
            >
              <td class="py-1.5 px-2 text-slate-400">
                {{ player.jersey_number }}
              </td>
              <td class="py-1.5 px-2 text-white">
                {{ playerDisplayName(player) }}
              </td>
              <td class="text-center py-1.5 px-2">
                <input
                  v-if="canEdit"
                  type="checkbox"
                  v-model="player.started"
                  class="rounded bg-slate-700 border-slate-600 text-blue-500"
                />
                <span v-else class="text-slate-300">{{
                  player.started ? 'Y' : '-'
                }}</span>
              </td>
              <td class="text-center py-1.5 px-2">
                <input
                  v-if="canEdit"
                  type="number"
                  v-model.number="player.minutes_played"
                  min="0"
                  max="130"
                  class="w-14 bg-slate-700 text-white text-sm text-center rounded px-1 py-0.5 border border-slate-600"
                />
                <span v-else class="text-slate-300">{{
                  player.minutes_played
                }}</span>
              </td>
              <td class="text-center py-1.5 px-2 text-slate-300">
                {{ player.goals }}
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="canEdit" class="mt-3 flex justify-end">
          <button
            @click="submitStats"
            :disabled="saving"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:text-slate-400 text-white text-sm rounded font-medium transition-colors"
          >
            {{ saving ? 'Saving...' : 'Save Player Stats' }}
          </button>
        </div>
      </div>
      <div v-else class="text-slate-500 text-xs">
        No roster players found for this team.
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue';

export default {
  name: 'TeamStatsPanel',
  props: {
    teamId: { type: Number, required: true },
    teamName: { type: String, default: '' },
    roster: { type: Array, default: () => [] },
    events: { type: Array, default: () => [] },
    playerStats: { type: Array, default: () => [] },
    canEdit: { type: Boolean, default: false },
    saving: { type: Boolean, default: false },
    error: { type: String, default: null },
  },
  emits: [
    'add-goal',
    'remove-goal',
    'add-substitution',
    'remove-substitution',
    'save-stats',
  ],
  setup(props, { emit }) {
    // Goal form
    const goalForm = ref({
      player_id: '',
      match_minute: null,
      extra_time: null,
    });

    // Substitution form
    const subForm = ref({
      player_in_id: '',
      player_out_id: '',
      match_minute: null,
      extra_time: null,
    });

    // Editable copy of player stats
    const editableStats = ref([]);

    // Sync editable stats when playerStats prop changes
    watch(
      () => props.playerStats,
      newStats => {
        editableStats.value = newStats.map(s => ({ ...s }));
      },
      { immediate: true, deep: true }
    );

    // Filtered events
    const goalEvents = computed(() =>
      props.events
        .filter(e => e.event_type === 'goal')
        .sort((a, b) => (a.match_minute || 0) - (b.match_minute || 0))
    );

    const subEvents = computed(() =>
      props.events
        .filter(e => e.event_type === 'substitution')
        .sort((a, b) => (a.match_minute || 0) - (b.match_minute || 0))
    );

    function formatMinute(event) {
      if (!event.match_minute) return '';
      if (event.extra_time) {
        return `${event.match_minute}+${event.extra_time}'`;
      }
      return `${event.match_minute}'`;
    }

    function playerDisplayName(player) {
      const name =
        `${player.first_name || ''} ${player.last_name || ''}`.trim();
      return name || `#${player.jersey_number}`;
    }

    function submitGoal() {
      const data = {
        team_id: props.teamId,
        player_id: goalForm.value.player_id,
        match_minute: goalForm.value.match_minute,
      };
      if (goalForm.value.extra_time) {
        data.extra_time = goalForm.value.extra_time;
      }
      emit('add-goal', data);
      goalForm.value = { player_id: '', match_minute: null, extra_time: null };
    }

    function submitSubstitution() {
      const data = {
        team_id: props.teamId,
        player_in_id: subForm.value.player_in_id,
        player_out_id: subForm.value.player_out_id,
        match_minute: subForm.value.match_minute,
      };
      if (subForm.value.extra_time) {
        data.extra_time = subForm.value.extra_time;
      }
      emit('add-substitution', data);
      subForm.value = {
        player_in_id: '',
        player_out_id: '',
        match_minute: null,
        extra_time: null,
      };
    }

    function submitStats() {
      const entries = editableStats.value.map(s => ({
        player_id: s.player_id,
        started: s.started,
        minutes_played: s.minutes_played,
      }));
      emit('save-stats', props.teamId, entries);
    }

    return {
      goalForm,
      subForm,
      editableStats,
      goalEvents,
      subEvents,
      formatMinute,
      playerDisplayName,
      submitGoal,
      submitSubstitution,
      submitStats,
    };
  },
};
</script>
