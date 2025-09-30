<template>
  <div v-if="show" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Edit Game</h3>

        <form @submit.prevent="updateGame()">
          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Date</label
              >
              <input
                v-model="formData.game_date"
                type="date"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Game Type</label
              >
              <select
                v-model="formData.game_type_id"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option
                  v-for="gameType in gameTypes"
                  :key="gameType.id"
                  :value="gameType.id"
                >
                  {{ gameType.name }}
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
              {{ loading ? 'Updating...' : 'Update Game' }}
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
  name: 'GameEditModal',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    game: {
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
    gameTypes: {
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
      game_date: '',
      home_team_id: '',
      away_team_id: '',
      home_score: null,
      away_score: null,
      game_type_id: '',
      season_id: '',
      age_group_id: '',
      division_id: null,
    });

    // Watch for game prop changes to populate form
    watch(
      () => props.game,
      newGame => {
        if (newGame) {
          formData.value = {
            game_date: newGame.game_date,
            home_team_id: newGame.home_team_id,
            away_team_id: newGame.away_team_id,
            home_score: newGame.home_score,
            away_score: newGame.away_score,
            game_type_id: newGame.game_type_id,
            season_id: newGame.season_id,
            age_group_id: newGame.age_group_id,
            division_id: newGame.division_id,
          };
          error.value = null;
        }
      },
      { immediate: true }
    );

    const updateGame = async () => {
      if (!props.game) return;

      try {
        loading.value = true;
        error.value = null;

        // Convert empty scores to 0 for API
        const gameData = {
          ...formData.value,
          home_score: formData.value.home_score || 0,
          away_score: formData.value.away_score || 0,
        };

        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/games/${props.game.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(gameData),
          }
        );

        emit('updated');
        emit('close');
      } catch (err) {
        console.error('Update game error:', err);
        if (
          err.message.includes('401') ||
          err.message.includes('Invalid or expired token') ||
          err.message.includes('Session expired')
        ) {
          error.value =
            'Your session has expired. Please refresh the page or log out and log back in to continue.';
        } else {
          error.value = err.message || 'Failed to update game';
        }
      } finally {
        loading.value = false;
      }
    };

    return {
      formData,
      loading,
      error,
      updateGame,
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
