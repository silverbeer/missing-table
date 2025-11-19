<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Matches Management</h3>
      <div class="flex space-x-3">
        <!-- Filters -->
        <select
          v-model="filterSeason"
          @change="fetchMatches"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Seasons</option>
          <option v-for="season in seasons" :key="season.id" :value="season.id">
            {{ season.name }}
          </option>
        </select>

        <select
          v-model="filterMatchType"
          @change="fetchMatches"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Match Types</option>
          <option
            v-for="matchType in matchTypes"
            :key="matchType.id"
            :value="matchType.id"
          >
            {{ matchType.name }}
          </option>
        </select>

        <select
          v-model="filterAgeGroup"
          @change="fetchMatches"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Age Groups</option>
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

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-8">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
      ></div>
    </div>

    <!-- Error State -->
    <div
      v-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4 mb-4"
    >
      <div class="text-red-800">{{ error }}</div>
    </div>

    <!-- Games Table -->
    <div
      v-else
      class="overflow-x-auto shadow ring-1 ring-black ring-opacity-5 md:rounded-lg"
    >
      <table class="min-w-full divide-y divide-gray-300">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24"
            >
              Date
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Home Team
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Away Team
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20"
            >
              Score
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20"
            >
              Type
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24"
            >
              Season
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20"
            >
              Age Group
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24"
            >
              Status
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32"
            >
              Match ID
            </th>
            <th
              class="px-4 py-3 text-right text-xs font-medium text-gray-500 bg-gray-50 uppercase tracking-wider w-44 sticky right-0"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="match in matches" :key="match.id">
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
              {{ formatDate(match.match_date) }}
            </td>
            <td
              class="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ match.home_team_name }}
            </td>
            <td
              class="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ match.away_team_name }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                v-if="match.home_score !== null && match.away_score !== null"
              >
                {{ match.home_score }} - {{ match.away_score }}
              </span>
              <span v-else class="text-gray-400 italic">Not played</span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="getMatchTypeClass(match.match_type_name)"
              >
                {{ match.match_type_name }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ match.season_name }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ match.age_group_name }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="getStatusClass(match.status)"
              >
                {{ getStatusDisplay(match.status) }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                v-if="match.match_id"
                class="font-mono text-xs"
                :title="`External Match ID: ${match.match_id}`"
              >
                {{ match.match_id }}
              </span>
              <span v-else class="text-gray-400 italic text-xs">-</span>
            </td>
            <td
              class="px-4 py-4 whitespace-nowrap text-right text-sm font-medium bg-gray-50 w-44 sticky right-0"
            >
              <div class="flex gap-2 justify-end items-center">
                <button
                  @click="editMatch(match)"
                  class="bg-blue-500 text-white px-2 py-1.5 rounded hover:bg-blue-600 font-medium text-xs min-w-[60px]"
                >
                  ✏️ Edit
                </button>
                <button
                  @click="deleteMatch(match)"
                  class="bg-red-500 text-white px-2 py-1.5 rounded hover:bg-red-600 font-medium text-xs min-w-[70px]"
                  title="Delete this match"
                >
                  🗑️ Delete
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty state -->
      <div v-if="!loading && matches.length === 0" class="text-center py-12">
        <div class="text-gray-500">No matches found</div>
      </div>
    </div>

    <!-- Edit Match Modal -->
    <div v-if="showEditModal" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Edit Match</h3>

          <form @submit.prevent="updateMatch()">
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Date</label
                >
                <input
                  v-model="editFormData.match_date"
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
                  v-model="editFormData.match_type_id"
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
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Away Team</label
                >
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
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Home Score</label
                >
                <input
                  v-model.number="editFormData.home_score"
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
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Season</label
                >
                <select
                  v-model="editFormData.season_id"
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
                  v-model="editFormData.age_group_id"
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

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Match ID
                <span class="text-gray-400 text-xs"
                  >(optional - for externally scraped matches)</span
                ></label
              >
              <input
                v-model="editFormData.match_id"
                type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                placeholder="e.g., external-match-12345"
              />
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
                {{ formLoading ? 'Updating...' : 'Update Match' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'AdminMatches',
  setup() {
    const authStore = useAuthStore();
    const matches = ref([]);
    const teams = ref([]);
    const seasons = ref([]);
    const matchTypes = ref([]);
    const ageGroups = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showEditModal = ref(false);
    const editingMatch = ref(null);
    const filterSeason = ref('');
    const filterMatchType = ref('');
    const filterAgeGroup = ref('');

    const editFormData = ref({
      match_date: '',
      home_team_id: '',
      away_team_id: '',
      home_score: null,
      away_score: null,
      match_type_id: '',
      season_id: '',
      age_group_id: '',
      division_id: null,
      match_id: '',
    });

    const fetchMatches = async () => {
      try {
        loading.value = true;
        let url = `${getApiBaseUrl()}/api/matches`;
        const params = new URLSearchParams();

        if (filterSeason.value) params.append('season_id', filterSeason.value);
        if (filterMatchType.value) {
          // Find the match type name from the ID
          const matchType = matchTypes.value.find(
            gt => gt.id == filterMatchType.value
          );
          if (matchType) {
            params.append('match_type', matchType.name);
          }
        }
        if (filterAgeGroup.value)
          params.append('age_group_id', filterAgeGroup.value);

        if (params.toString()) {
          url += `?${params.toString()}`;
        }

        const response = await authStore.apiRequest(url, {
          method: 'GET',
        });
        matches.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchReferenceData = async () => {
      try {
        const [teamsData, seasonsData, matchTypesData, ageGroupsData] =
          await Promise.all([
            authStore.apiRequest(`${getApiBaseUrl()}/api/teams`, {
              method: 'GET',
            }),
            authStore.apiRequest(`${getApiBaseUrl()}/api/seasons`, {
              method: 'GET',
            }),
            authStore.apiRequest(`${getApiBaseUrl()}/api/match-types`, {
              method: 'GET',
            }),
            authStore.apiRequest(`${getApiBaseUrl()}/api/age-groups`, {
              method: 'GET',
            }),
          ]);

        teams.value = teamsData;
        seasons.value = seasonsData;
        matchTypes.value = matchTypesData;
        if (ageGroupsData) {
          ageGroups.value = ageGroupsData;
          // Set U14 as default filter
          const u14AgeGroup = ageGroups.value.find(ag => ag.name === 'U14');
          if (u14AgeGroup) {
            filterAgeGroup.value = u14AgeGroup.id;
          }
        }
      } catch (err) {
        console.error('Error fetching reference data:', err);
      }
    };

    const formatDate = dateString => {
      return new Date(dateString).toLocaleDateString();
    };

    const getMatchTypeClass = matchTypeName => {
      const classes = {
        League: 'bg-blue-100 text-blue-800',
        Friendly: 'bg-green-100 text-green-800',
        Tournament: 'bg-purple-100 text-purple-800',
        Playoff: 'bg-orange-100 text-orange-800',
      };
      return classes[matchTypeName] || 'bg-gray-100 text-gray-800';
    };

    const getStatusClass = status => {
      const classes = {
        scheduled: 'bg-yellow-100 text-yellow-800',
        completed: 'bg-green-100 text-green-800',
        postponed: 'bg-orange-100 text-orange-800',
        cancelled: 'bg-red-100 text-red-800',
      };
      return classes[status] || 'bg-gray-100 text-gray-800';
    };

    const getStatusDisplay = status => {
      if (!status) {
        // Fallback for matches without status field (backward compatibility)
        return 'Unknown';
      }
      // Capitalize first letter
      return status.charAt(0).toUpperCase() + status.slice(1);
    };

    const editMatch = match => {
      editingMatch.value = match;
      editFormData.value = {
        match_date: match.match_date,
        home_team_id: match.home_team_id,
        away_team_id: match.away_team_id,
        home_score: match.home_score,
        away_score: match.away_score,
        match_type_id: match.match_type_id,
        season_id: match.season_id,
        age_group_id: match.age_group_id,
        division_id: match.division_id,
        match_id: match.match_id || '',
      };
      showEditModal.value = true;
    };

    const updateMatch = async () => {
      try {
        formLoading.value = true;

        // Convert empty scores to 0 for API
        const matchData = {
          ...editFormData.value,
          home_score: editFormData.value.home_score || 0,
          away_score: editFormData.value.away_score || 0,
        };

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${editingMatch.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(matchData),
          }
        );

        await fetchMatches();
        closeEditModal();
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
        formLoading.value = false;
      }
    };

    const deleteMatch = async match => {
      if (
        !confirm(
          `Are you sure you want to delete the match between ${match.home_team_name} and ${match.away_team_name} on ${formatDate(match.match_date)}?`
        )
      ) {
        return;
      }

      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${match.id}`,
          {
            method: 'DELETE',
          }
        );

        await fetchMatches();
      } catch (err) {
        console.error('Delete match error:', err);
        if (
          err.message.includes('401') ||
          err.message.includes('Invalid or expired token') ||
          err.message.includes('Session expired')
        ) {
          error.value =
            'Your session has expired. Please refresh the page or log out and log back in to continue.';
        } else {
          error.value = err.message || 'Failed to delete match';
        }
      }
    };

    const closeEditModal = () => {
      showEditModal.value = false;
      editingMatch.value = null;
      editFormData.value = {
        match_date: '',
        home_team_id: '',
        away_team_id: '',
        home_score: null,
        away_score: null,
        match_type_id: '',
        season_id: '',
        age_group_id: '',
        division_id: null,
      };
    };

    onMounted(async () => {
      await Promise.all([fetchMatches(), fetchReferenceData()]);
    });

    return {
      matches,
      teams,
      seasons,
      matchTypes,
      ageGroups,
      loading,
      formLoading,
      error,
      showEditModal,
      editFormData,
      filterSeason,
      filterMatchType,
      filterAgeGroup,
      fetchMatches,
      formatDate,
      getMatchTypeClass,
      getStatusClass,
      getStatusDisplay,
      editMatch,
      updateMatch,
      deleteMatch,
      closeEditModal,
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
