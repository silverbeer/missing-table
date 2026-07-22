<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-fg">Seasons Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Season
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-8">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
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
      class="overflow-x-auto shadow ring-1 ring-black ring-opacity-5 md:rounded-lg"
    >
      <table class="min-w-full divide-y divide-line">
        <thead class="bg-surface-alt">
          <tr>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Name
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Start Date
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              End Date
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              data-testid="matches-count-header"
            >
              Matches Count
            </th>
            <th
              class="px-6 py-3 text-right text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-card divide-y divide-line">
          <tr
            v-for="season in seasons"
            :key="season.id"
            :class="{ 'bg-brand-50': season.is_current }"
          >
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-fg">
              {{ season.name }}
              <span
                v-if="season.is_current"
                class="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-brand-100 text-brand-800"
                data-testid="current-season-badge"
              >
                Current
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted">
              {{ formatDate(season.start_date) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted">
              {{ formatDate(season.end_date) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted"
              :data-testid="`matches-count-${season.id}`"
            >
              {{ getMatchesCount(season.id) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                v-if="!season.is_current"
                @click="setCurrentSeason(season)"
                class="text-green-600 hover:text-green-900 mr-3"
                :data-testid="`set-current-${season.id}`"
              >
                Set current
              </button>
              <button
                @click="editSeason(season)"
                class="text-brand-600 dark:text-brand-300 hover:text-brand-900 dark:hover:text-brand-200 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteSeason(season)"
                class="text-red-600 hover:text-red-900"
                :disabled="getMatchesCount(season.id) > 0"
                :class="{
                  'opacity-50 cursor-not-allowed':
                    getMatchesCount(season.id) > 0,
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
          <h3 class="text-lg font-medium text-fg mb-4">
            {{ showEditModal ? 'Edit Season' : 'Add New Season' }}
          </h3>

          <form
            @submit.prevent="showEditModal ? updateSeason() : createSeason()"
          >
            <div class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2"
                >Season Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="e.g., 2024-2025, 2025-2026..."
              />
            </div>

            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-fg mb-2"
                  >Start Date</label
                >
                <input
                  v-model="formData.start_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-fg mb-2"
                  >End Date</label
                >
                <input
                  v-model="formData.end_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            <div class="mb-4">
              <label class="inline-flex items-center">
                <input
                  type="checkbox"
                  v-model="formData.is_current"
                  class="rounded border-line text-brand-600 focus:ring-brand-500"
                  data-testid="season-is-current-checkbox"
                />
                <span class="ml-2 text-sm text-fg">Set as current season</span>
              </label>
              <p class="mt-1 text-xs text-fg-muted">
                Season dropdowns across the app default to the current season.
                Setting this clears the flag from any other season.
              </p>
            </div>

            <div class="flex justify-end space-x-3">
              <button
                type="button"
                @click="closeModals"
                class="px-4 py-2 text-sm font-medium text-fg bg-surface-alt hover:bg-line rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="formLoading"
                class="px-4 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-md disabled:opacity-50"
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
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'AdminSeasons',
  setup() {
    const authStore = useAuthStore();
    const seasons = ref([]);
    // Map of season_id → match_count from /api/seasons/match-counts.
    // Replaces the prior approach of fetching all matches and filtering
    // client-side (capped at Supabase's 1000-row default — see SB-61).
    const matchCountsBySeasonId = ref({});
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
      is_current: false,
    });

    const fetchSeasons = async () => {
      try {
        loading.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons`,
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

    const setCurrentSeason = async season => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons/${season.id}/current`,
          { method: 'PUT' }
        );
        await fetchSeasons();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const fetchMatchCounts = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons/match-counts`,
          { method: 'GET' }
        );
        const map = {};
        for (const row of response || []) {
          map[row.season_id] = row.match_count ?? 0;
        }
        matchCountsBySeasonId.value = map;
      } catch (err) {
        console.error('Error fetching match counts:', err);
      }
    };

    const getMatchesCount = seasonId => {
      return matchCountsBySeasonId.value[seasonId] ?? 0;
    };

    const formatDate = dateString => {
      return new Date(dateString + 'T00:00:00').toLocaleDateString();
    };

    const createSeason = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(`${getApiBaseUrl()}/api/seasons`, {
          method: 'POST',
          body: JSON.stringify(formData.value),
        });

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
          `${getApiBaseUrl()}/api/seasons/${editingSeason.value.id}`,
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
      if (getMatchesCount(season.id) > 0) {
        error.value = 'Cannot delete season with associated matches';
        return;
      }

      if (!confirm(`Are you sure you want to delete "${season.name}"?`)) return;

      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons/${season.id}`,
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
        is_current: false,
      };
    };

    onMounted(async () => {
      await Promise.all([fetchSeasons(), fetchMatchCounts()]);
    });

    return {
      seasons,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      formData,
      getMatchesCount,
      formatDate,
      createSeason,
      editSeason,
      updateSeason,
      deleteSeason,
      setCurrentSeason,
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
  background: rgb(var(--color-card));
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>
