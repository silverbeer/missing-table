<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Goals Management</h3>
      <div class="flex space-x-3">
        <select
          v-model="filterSeason"
          @change="fetchGoals"
          class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Seasons</option>
          <option v-for="season in seasons" :key="season.id" :value="season.id">
            {{ season.name }}
          </option>
        </select>

        <select
          v-model="filterAgeGroup"
          @change="fetchGoals"
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

        <select
          v-model="filterMatchType"
          @change="fetchGoals"
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

    <!-- Goals Table -->
    <div
      v-else
      class="overflow-x-auto shadow ring-1 ring-black ring-opacity-5 md:rounded-lg"
    >
      <table class="min-w-full divide-y divide-gray-300">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Match
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24"
            >
              Date
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Scorer
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20"
            >
              Minute
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24"
            >
              Season
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24"
            >
              Age Group
            </th>
            <th
              class="px-4 py-3 text-right text-xs font-medium text-gray-500 bg-gray-50 uppercase tracking-wider w-44 sticky right-0"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="goal in goals" :key="goal.id">
            <td
              class="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ getHomeTeamName(goal) }} vs {{ getAwayTeamName(goal) }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(goal.match?.match_date) }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
              {{ goal.player_name || 'Unknown' }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatMinute(goal.match_minute, goal.extra_time) }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ goal.match?.season?.name || '-' }}
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ goal.match?.age_group?.name || '-' }}
            </td>
            <td
              class="px-4 py-4 whitespace-nowrap text-right text-sm font-medium bg-gray-50 w-44 sticky right-0"
            >
              <div class="flex gap-2 justify-end items-center">
                <button
                  @click="editGoal(goal)"
                  class="bg-blue-500 text-white px-2 py-1.5 rounded hover:bg-blue-600 font-medium text-xs min-w-[60px]"
                >
                  Edit
                </button>
                <button
                  @click="deleteGoal(goal)"
                  class="bg-red-500 text-white px-2 py-1.5 rounded hover:bg-red-600 font-medium text-xs min-w-[70px]"
                  title="Delete this goal"
                >
                  Delete
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty state -->
      <div v-if="!loading && goals.length === 0" class="text-center py-12">
        <div class="text-gray-500">No goals found</div>
      </div>
    </div>

    <!-- Edit Goal Modal -->
    <div v-if="showEditModal" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Edit Goal</h3>

          <div class="mb-4 text-sm text-gray-600">
            <span class="font-medium">Match:</span>
            {{ getHomeTeamName(editingGoal) }} vs
            {{ getAwayTeamName(editingGoal) }} ({{
              formatDate(editingGoal?.match?.match_date)
            }})
          </div>

          <form @submit.prevent="updateGoal()">
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Match Minute</label
                >
                <input
                  v-model.number="editFormData.match_minute"
                  type="number"
                  min="0"
                  max="120"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. 45"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Extra Time</label
                >
                <input
                  v-model.number="editFormData.extra_time"
                  type="number"
                  min="0"
                  max="30"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. 3"
                />
              </div>
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Player Name</label
              >
              <input
                v-model="editFormData.player_name"
                type="text"
                maxlength="200"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Goal scorer name"
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
                {{ formLoading ? 'Saving...' : 'Save Changes' }}
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
  name: 'AdminGoals',
  setup() {
    const authStore = useAuthStore();
    const goals = ref([]);
    const seasons = ref([]);
    const matchTypes = ref([]);
    const ageGroups = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showEditModal = ref(false);
    const editingGoal = ref(null);
    const filterSeason = ref('');
    const filterMatchType = ref('');
    const filterAgeGroup = ref('');

    const editFormData = ref({
      match_minute: null,
      extra_time: null,
      player_name: '',
    });

    const fetchGoals = async () => {
      try {
        loading.value = true;
        error.value = null;
        let url = `${getApiBaseUrl()}/api/admin/goals`;
        const params = new URLSearchParams();

        if (filterSeason.value) params.append('season_id', filterSeason.value);
        if (filterAgeGroup.value)
          params.append('age_group_id', filterAgeGroup.value);
        if (filterMatchType.value)
          params.append('match_type_id', filterMatchType.value);

        if (params.toString()) {
          url += `?${params.toString()}`;
        }

        const response = await authStore.apiRequest(url, { method: 'GET' });
        goals.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchReferenceData = async () => {
      try {
        const [seasonsData, matchTypesData, ageGroupsData] = await Promise.all([
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

        seasons.value = seasonsData || [];
        matchTypes.value = matchTypesData || [];
        ageGroups.value = ageGroupsData || [];
      } catch (err) {
        console.error('Error fetching reference data:', err);
      }
    };

    const getHomeTeamName = goal => {
      return goal?.match?.home_team?.name || 'Unknown';
    };

    const getAwayTeamName = goal => {
      return goal?.match?.away_team?.name || 'Unknown';
    };

    const formatDate = dateString => {
      if (!dateString) return '-';
      return new Date(dateString).toLocaleDateString();
    };

    const formatMinute = (minute, extraTime) => {
      if (minute == null) return '-';
      if (extraTime) {
        return `${minute}+${extraTime}'`;
      }
      return `${minute}'`;
    };

    const editGoal = goal => {
      editingGoal.value = goal;
      editFormData.value = {
        match_minute: goal.match_minute,
        extra_time: goal.extra_time,
        player_name: goal.player_name || '',
      };
      showEditModal.value = true;
    };

    const updateGoal = async () => {
      try {
        formLoading.value = true;

        const body = {};
        if (
          editFormData.value.match_minute !== null &&
          editFormData.value.match_minute !== editingGoal.value.match_minute
        ) {
          body.match_minute = editFormData.value.match_minute;
        }
        if (
          editFormData.value.extra_time !== null &&
          editFormData.value.extra_time !== editingGoal.value.extra_time
        ) {
          body.extra_time = editFormData.value.extra_time;
        }
        if (
          editFormData.value.player_name &&
          editFormData.value.player_name !== editingGoal.value.player_name
        ) {
          body.player_name = editFormData.value.player_name;
        }

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/goals/${editingGoal.value.id}`,
          {
            method: 'PATCH',
            body: JSON.stringify(body),
          }
        );

        await fetchGoals();
        closeEditModal();
      } catch (err) {
        console.error('Update goal error:', err);
        if (
          err.message.includes('401') ||
          err.message.includes('Invalid or expired token') ||
          err.message.includes('Session expired')
        ) {
          error.value =
            'Your session has expired. Please refresh the page or log out and log back in to continue.';
        } else {
          error.value = err.message || 'Failed to update goal';
        }
      } finally {
        formLoading.value = false;
      }
    };

    const deleteGoal = async goal => {
      const scorer = goal.player_name || 'Unknown';
      const matchDesc = `${getHomeTeamName(goal)} vs ${getAwayTeamName(goal)}`;
      if (
        !confirm(
          `Are you sure you want to delete the goal by ${scorer} in ${matchDesc}? This will also update the match score.`
        )
      ) {
        return;
      }

      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${goal.match_id}/live/events/${goal.id}`,
          { method: 'DELETE' }
        );

        await fetchGoals();
      } catch (err) {
        console.error('Delete goal error:', err);
        if (
          err.message.includes('401') ||
          err.message.includes('Invalid or expired token') ||
          err.message.includes('Session expired')
        ) {
          error.value =
            'Your session has expired. Please refresh the page or log out and log back in to continue.';
        } else {
          error.value = err.message || 'Failed to delete goal';
        }
      }
    };

    const closeEditModal = () => {
      showEditModal.value = false;
      editingGoal.value = null;
      editFormData.value = {
        match_minute: null,
        extra_time: null,
        player_name: '',
      };
    };

    onMounted(async () => {
      await Promise.all([fetchGoals(), fetchReferenceData()]);
    });

    return {
      goals,
      seasons,
      matchTypes,
      ageGroups,
      loading,
      formLoading,
      error,
      showEditModal,
      editingGoal,
      editFormData,
      filterSeason,
      filterMatchType,
      filterAgeGroup,
      fetchGoals,
      getHomeTeamName,
      getAwayTeamName,
      formatDate,
      formatMinute,
      editGoal,
      updateGoal,
      deleteGoal,
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
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>
