<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Seasons Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Season
      </button>
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

    <!-- Seasons Table -->
    <div
      v-else
      class="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg"
    >
      <table class="min-w-full divide-y divide-gray-300">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Name
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Start Date
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              End Date
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Games Count
            </th>
            <th
              class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr
            v-for="season in seasons"
            :key="season.id"
            :class="{ 'bg-blue-50': isCurrentSeason(season) }"
          >
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ season.name }}
              <span
                v-if="isCurrentSeason(season)"
                class="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
              >
                Current
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(season.start_date) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(season.end_date) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ getGamesCount(season.id) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                @click="editSeason(season)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteSeason(season)"
                class="text-red-600 hover:text-red-900"
                :disabled="getGamesCount(season.id) > 0"
                :class="{
                  'opacity-50 cursor-not-allowed': getGamesCount(season.id) > 0,
                }"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add/Edit Modal -->
    <div
      v-if="showAddModal || showEditModal"
      class="modal-overlay"
      @click="closeModals"
    >
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            {{ showEditModal ? 'Edit Season' : 'Add New Season' }}
          </h3>

          <form
            @submit.prevent="showEditModal ? updateSeason() : createSeason()"
          >
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Season Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., 2024-2025, 2025-2026..."
              />
            </div>

            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >Start Date</label
                >
                <input
                  v-model="formData.start_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >End Date</label
                >
                <input
                  v-model="formData.end_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div class="flex justify-end space-x-3">
              <button
                type="button"
                @click="closeModals"
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="formLoading"
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
              >
                {{
                  formLoading
                    ? 'Saving...'
                    : showEditModal
                      ? 'Update'
                      : 'Create'
                }}
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

export default {
  name: 'AdminSeasons',
  setup() {
    const authStore = useAuthStore();
    const seasons = ref([]);
    const games = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const editingSeason = ref(null);

    const formData = ref({
      name: '',
      start_date: '',
      end_date: '',
    });

    const fetchSeasons = async () => {
      try {
        loading.value = true;
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons`,
          {
            method: 'GET',
          }
        );
        seasons.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchGames = async () => {
      try {
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/matches`,
          {
            method: 'GET',
          }
        );
        games.value = response;
      } catch (err) {
        console.error('Error fetching games:', err);
      }
    };

    const getGamesCount = seasonId => {
      return games.value.filter(game => game.season_id === seasonId).length;
    };

    const isCurrentSeason = season => {
      const now = new Date();
      const startDate = new Date(season.start_date);
      const endDate = new Date(season.end_date);
      return now >= startDate && now <= endDate;
    };

    const formatDate = dateString => {
      return new Date(dateString).toLocaleDateString();
    };

    const createSeason = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons`,
          {
            method: 'POST',
            body: JSON.stringify(formData.value),
          }
        );

        await fetchSeasons();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const editSeason = season => {
      editingSeason.value = season;
      formData.value = { ...season };
      showEditModal.value = true;
    };

    const updateSeason = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons/${editingSeason.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(formData.value),
          }
        );

        await fetchSeasons();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const deleteSeason = async season => {
      if (getGamesCount(season.id) > 0) {
        error.value = 'Cannot delete season with associated games';
        return;
      }

      if (!confirm(`Are you sure you want to delete "${season.name}"?`)) return;

      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons/${season.id}`,
          {
            method: 'DELETE',
          }
        );

        await fetchSeasons();
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      editingSeason.value = null;
      resetForm();
    };

    const resetForm = () => {
      formData.value = {
        name: '',
        start_date: '',
        end_date: '',
      };
    };

    onMounted(async () => {
      await Promise.all([fetchSeasons(), fetchGames()]);
    });

    return {
      seasons,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      formData,
      getGamesCount,
      isCurrentSeason,
      formatDate,
      createSeason,
      editSeason,
      updateSeason,
      deleteSeason,
      closeModals,
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
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>
