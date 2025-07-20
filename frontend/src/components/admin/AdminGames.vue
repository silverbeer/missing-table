<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Games Management</h3>
      <div class="flex space-x-3">
        <!-- Filters -->
        <select
          v-model="filterSeason"
          @change="fetchGames"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Seasons</option>
          <option v-for="season in seasons" :key="season.id" :value="season.id">
            {{ season.name }}
          </option>
        </select>
        
        <select
          v-model="filterGameType"
          @change="fetchGames"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Game Types</option>
          <option v-for="gameType in gameTypes" :key="gameType.id" :value="gameType.id">
            {{ gameType.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
      <div class="text-red-800">{{ error }}</div>
    </div>

    <!-- Games Table -->
    <div v-else class="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
      <table class="min-w-full divide-y divide-gray-300">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Home Team</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Away Team</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Season</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Age Group</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="game in games" :key="game.id">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
              {{ formatDate(game.game_date) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
              {{ game.home_team_name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
              {{ game.away_team_name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <span v-if="game.home_score !== null && game.away_score !== null">
                {{ game.home_score }} - {{ game.away_score }}
              </span>
              <span v-else class="text-gray-400 italic">Not played</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                    :class="getGameTypeClass(game.game_type_name)">
                {{ game.game_type_name }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ game.season_name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ game.age_group_name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
              <button
                @click="editGame(game)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteGame(game)"
                class="text-red-600 hover:text-red-900"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      
      <!-- Empty state -->
      <div v-if="!loading && games.length === 0" class="text-center py-12">
        <div class="text-gray-500">No games found</div>
      </div>
    </div>

    <!-- Edit Game Modal -->
    <div v-if="showEditModal" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Edit Game</h3>
          
          <form @submit.prevent="updateGame()">
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Date</label>
                <input
                  v-model="editFormData.game_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Game Type</label>
                <select
                  v-model="editFormData.game_type_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option v-for="gameType in gameTypes" :key="gameType.id" :value="gameType.id">
                    {{ gameType.name }}
                  </option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Home Team</label>
                <select
                  v-model="editFormData.home_team_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option v-for="team in teams" :key="team.id" :value="team.id">
                    {{ team.name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Away Team</label>
                <select
                  v-model="editFormData.away_team_id"
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
                <label class="block text-sm font-medium text-gray-700 mb-2">Home Score</label>
                <input
                  v-model.number="editFormData.home_score"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Leave empty if not played"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Away Score</label>
                <input
                  v-model.number="editFormData.away_score"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Leave empty if not played"
                />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Season</label>
                <select
                  v-model="editFormData.season_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option v-for="season in seasons" :key="season.id" :value="season.id">
                    {{ season.name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Age Group</label>
                <select
                  v-model="editFormData.age_group_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option v-for="ageGroup in ageGroups" :key="ageGroup.id" :value="ageGroup.id">
                    {{ ageGroup.name }}
                  </option>
                </select>
              </div>
            </div>
            
            <div class="flex justify-end space-x-3">
              <button
                type="button"
                @click="closeEditModal"
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="formLoading"
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
              >
                {{ formLoading ? 'Updating...' : 'Update Game' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

export default {
  name: 'AdminGames',
  setup() {
    const authStore = useAuthStore()
    const games = ref([])
    const teams = ref([])
    const seasons = ref([])
    const gameTypes = ref([])
    const ageGroups = ref([])
    const loading = ref(true)
    const formLoading = ref(false)
    const error = ref(null)
    const showEditModal = ref(false)
    const editingGame = ref(null)
    const filterSeason = ref('')
    const filterGameType = ref('')

    const editFormData = ref({
      game_date: '',
      home_team_id: '',
      away_team_id: '',
      home_score: null,
      away_score: null,
      game_type_id: '',
      season_id: '',
      age_group_id: '',
      division_id: null
    })

    const fetchGames = async () => {
      try {
        loading.value = true
        let url = 'http://localhost:8000/api/games'
        const params = new URLSearchParams()
        
        if (filterSeason.value) params.append('season_id', filterSeason.value)
        if (filterGameType.value) params.append('game_type', filterGameType.value)
        
        if (params.toString()) {
          url += `?${params.toString()}`
        }
        
        const response = await fetch(url)
        if (!response.ok) throw new Error('Failed to fetch games')
        games.value = await response.json()
      } catch (err) {
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    const fetchReferenceData = async () => {
      try {
        const [teamsRes, seasonsRes, gameTypesRes, ageGroupsRes] = await Promise.all([
          fetch('http://localhost:8000/api/teams'),
          fetch('http://localhost:8000/api/seasons'),
          fetch('http://localhost:8000/api/game-types'),
          fetch('http://localhost:8000/api/age-groups')
        ])

        if (teamsRes.ok) teams.value = await teamsRes.json()
        if (seasonsRes.ok) seasons.value = await seasonsRes.json()
        if (gameTypesRes.ok) gameTypes.value = await gameTypesRes.json()
        if (ageGroupsRes.ok) ageGroups.value = await ageGroupsRes.json()
      } catch (err) {
        console.error('Error fetching reference data:', err)
      }
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleDateString()
    }

    const getGameTypeClass = (gameTypeName) => {
      const classes = {
        'League': 'bg-blue-100 text-blue-800',
        'Friendly': 'bg-green-100 text-green-800',
        'Tournament': 'bg-purple-100 text-purple-800',
        'Playoff': 'bg-orange-100 text-orange-800'
      }
      return classes[gameTypeName] || 'bg-gray-100 text-gray-800'
    }

    const editGame = (game) => {
      editingGame.value = game
      editFormData.value = {
        game_date: game.game_date,
        home_team_id: game.home_team_id,
        away_team_id: game.away_team_id,
        home_score: game.home_score,
        away_score: game.away_score,
        game_type_id: game.game_type_id,
        season_id: game.season_id,
        age_group_id: game.age_group_id,
        division_id: game.division_id
      }
      showEditModal.value = true
    }

    const updateGame = async () => {
      try {
        formLoading.value = true
        
        // Convert empty scores to 0 for API
        const gameData = {
          ...editFormData.value,
          home_score: editFormData.value.home_score || 0,
          away_score: editFormData.value.away_score || 0
        }
        
        await authStore.apiRequest(`http://localhost:8000/api/games/${editingGame.value.id}`, {
          method: 'PUT',
          body: JSON.stringify(gameData)
        })
        
        await fetchGames()
        closeEditModal()
      } catch (err) {
        console.error('Update game error:', err)
        if (err.message.includes('401') || err.message.includes('Invalid or expired token') || err.message.includes('Session expired')) {
          error.value = 'Your session has expired. Please refresh the page or log out and log back in to continue.'
        } else {
          error.value = err.message || 'Failed to update game'
        }
      } finally {
        formLoading.value = false
      }
    }

    const deleteGame = async (game) => {
      if (!confirm(`Are you sure you want to delete the game between ${game.home_team_name} and ${game.away_team_name} on ${formatDate(game.game_date)}?`)) {
        return
      }

      try {
        await authStore.apiRequest(`http://localhost:8000/api/games/${game.id}`, {
          method: 'DELETE'
        })
        
        await fetchGames()
      } catch (err) {
        console.error('Delete game error:', err)
        if (err.message.includes('401') || err.message.includes('Invalid or expired token') || err.message.includes('Session expired')) {
          error.value = 'Your session has expired. Please refresh the page or log out and log back in to continue.'
        } else {
          error.value = err.message || 'Failed to delete game'
        }
      }
    }

    const closeEditModal = () => {
      showEditModal.value = false
      editingGame.value = null
      editFormData.value = {
        game_date: '',
        home_team_id: '',
        away_team_id: '',
        home_score: null,
        away_score: null,
        game_type_id: '',
        season_id: '',
        age_group_id: '',
        division_id: null
      }
    }

    onMounted(async () => {
      await Promise.all([fetchGames(), fetchReferenceData()])
    })

    return {
      games,
      teams,
      seasons,
      gameTypes,
      ageGroups,
      loading,
      formLoading,
      error,
      showEditModal,
      editFormData,
      filterSeason,
      filterGameType,
      fetchGames,
      formatDate,
      getGameTypeClass,
      editGame,
      updateGame,
      deleteGame,
      closeEditModal
    }
  }
}
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
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 800px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>