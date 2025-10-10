<template>
  <div v-if="show" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Edit Match</h3>

        <!-- Audit Trail Info -->
        <div
          v-if="match && (match.created_at || match.updated_at)"
          class="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-md text-xs text-gray-600 space-y-1"
        >
          <div v-if="match.source" class="flex items-center space-x-2">
            <span class="font-medium">Source:</span>
            <span
              :class="{
                'px-2 py-0.5 rounded text-xs font-medium': true,
                'bg-purple-100 text-purple-800':
                  match.source === 'match-scraper',
                'bg-gray-100 text-gray-700': match.source === 'manual',
                'bg-yellow-100 text-yellow-700': match.source === 'import',
              }"
            >
              {{ getSourceText(match.source) }}
            </span>
          </div>
          <div v-if="match.created_at">
            <span class="font-medium">Created:</span>
            {{ formatDate(match.created_at) }}
          </div>
          <div v-if="match.updated_at">
            <span class="font-medium">Last Updated:</span>
            {{ formatDate(match.updated_at) }}
          </div>
        </div>

        <form @submit.prevent="updateMatch()">
          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Date</label
              >
              <input
                v-model="formData.match_date"
                type="date"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Match Type</label
              >
              <select
                v-model="formData.match_type_id"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option
                  v-for="matchType in matchTypes"
                  :key="matchType.id"
                  :value="matchType.id"
                >
                  {{ matchType.name }}
                </option>
              </select>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Home Team</label
              >
              <select
                v-model="formData.home_team_id"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="team in teams" :key="team.id" :value="team.id">
                  {{ team.name }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Away Team</label
              >
              <select
                v-model="formData.away_team_id"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option v-for="team in teams" :key="team.id" :value="team.id">
                  {{ team.name }}
                </option>
              </select>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Home Score</label
              >
              <input
                v-model.number="formData.home_score"
                type="number"
                min="0"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Leave empty if not played"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Away Score</label
              >
              <input
                v-model.number="formData.away_score"
                type="number"
                min="0"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Leave empty if not played"
              />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Season</label
              >
              <select
                v-model="formData.season_id"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option
                  v-for="season in seasons"
                  :key="season.id"
                  :value="season.id"
                >
                  {{ season.name }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Age Group</label
              >
              <select
                v-model="formData.age_group_id"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option
                  v-for="ageGroup in ageGroups"
                  :key="ageGroup.id"
                  :value="ageGroup.id"
                >
                  {{ ageGroup.name }}
                </option>
              </select>
            </div>
          </div>

          <!-- Error Display -->
          <div
            v-if="error"
            class="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm"
          >
            {{ error }}
          </div>

          <div class="flex justify-end space-x-3">
            <button
              type="button"
              @click="$emit('close')"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="loading"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
            >
              {{ loading ? 'Updating...' : 'Update Match' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';

export default {
  name: 'MatchEditModal',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    match: {
      type: Object,
      default: null,
    },
    teams: {
      type: Array,
      default: () => [],
    },
    seasons: {
      type: Array,
      default: () => [],
    },
    matchTypes: {
      type: Array,
      default: () => [],
    },
    ageGroups: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['close', 'updated'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const loading = ref(false);
    const error = ref(null);

    const formData = ref({
      match_date: '',
      home_team_id: '',
      away_team_id: '',
      home_score: null,
      away_score: null,
      match_type_id: '',
      season_id: '',
      age_group_id: '',
      division_id: null,
    });

    // Watch for match prop changes to populate form
    watch(
      () => props.match,
      newMatch => {
        if (newMatch) {
          formData.value = {
            match_date: newMatch.match_date,
            home_team_id: newMatch.home_team_id,
            away_team_id: newMatch.away_team_id,
            home_score: newMatch.home_score,
            away_score: newMatch.away_score,
            match_type_id: newMatch.match_type_id,
            season_id: newMatch.season_id,
            age_group_id: newMatch.age_group_id,
            division_id: newMatch.division_id,
          };
          error.value = null;
        }
      },
      { immediate: true }
    );

    const formatDate = dateString => {
      if (!dateString) return '';
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    };

    const getSourceText = source => {
      const sourceMap = {
        manual: 'Manually entered',
        'match-scraper': 'Auto-scraped',
        import: 'Imported from backup',
      };
      return sourceMap[source] || source;
    };

    const updateMatch = async () => {
      if (!props.match) return;

      try {
        loading.value = true;
        error.value = null;

        // Build match data for API
        const matchData = {
          ...formData.value,
        };

        // Parse scores - treat null/undefined/empty string as "no score entered"
        // Note: 0 is a valid score (e.g., 3-0 match)
        const homeScoreValue = formData.value.home_score;
        const awayScoreValue = formData.value.away_score;

        // Check if scores have been entered (not null, undefined, or empty string)
        const homeScoreEntered =
          homeScoreValue !== null &&
          homeScoreValue !== undefined &&
          homeScoreValue !== '';
        const awayScoreEntered =
          awayScoreValue !== null &&
          awayScoreValue !== undefined &&
          awayScoreValue !== '';

        // Convert to numbers, defaulting to 0 if not entered
        matchData.home_score = homeScoreEntered ? Number(homeScoreValue) : 0;
        matchData.away_score = awayScoreEntered ? Number(awayScoreValue) : 0;

        // Auto-set status: if BOTH scores are entered, mark as played
        matchData.status =
          homeScoreEntered && awayScoreEntered ? 'played' : 'scheduled';

        console.log('MatchEditModal - Update data:', {
          homeScoreValue,
          awayScoreValue,
          homeScoreEntered,
          awayScoreEntered,
          status: matchData.status,
          fullMatchData: matchData,
        });

        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/matches/${props.match.id}`,
          {
            method: 'PATCH',
            body: JSON.stringify(matchData),
          }
        );

        emit('updated');
        emit('close');
      } catch (err) {
        console.error('Update match error:', err);
        if (
          err.message.includes('401') ||
          err.message.includes('Invalid or expired token') ||
          err.message.includes('Session expired')
        ) {
          error.value =
            'Your session has expired. Please refresh the page or log out and log back in to continue.';
        } else {
          error.value = err.message || 'Failed to update match';
        }
      } finally {
        loading.value = false;
      }
    };

    return {
      formData,
      loading,
      error,
      updateMatch,
      formatDate,
      getSourceText,
    };
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>
