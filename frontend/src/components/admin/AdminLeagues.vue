<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Leagues Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add League
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

    <!-- Leagues Table -->
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
              Description
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Sport
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Divisions Count
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Active
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Created
            </th>
            <th
              class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="league in leagues" :key="league.id">
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ league.name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ league.description || 'N/A' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                :class="[
                  'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                  league.sport_type === 'futsal'
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-green-100 text-green-800',
                ]"
              >
                {{ league.sport_type === 'futsal' ? 'Futsal' : 'Soccer' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ getDivisionCount(league.id) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                :class="[
                  'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                  league.is_active
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800',
                ]"
              >
                {{ league.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(league.created_at) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                @click="editLeague(league)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteLeague(league)"
                class="text-red-600 hover:text-red-900"
                :disabled="getDivisionCount(league.id) > 0"
                :class="{
                  'opacity-50 cursor-not-allowed':
                    getDivisionCount(league.id) > 0,
                }"
                :title="
                  getDivisionCount(league.id) > 0
                    ? 'Cannot delete league with divisions'
                    : 'Delete league'
                "
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
            {{ showEditModal ? 'Edit League' : 'Add New League' }}
          </h3>

          <form
            @submit.prevent="showEditModal ? updateLeague() : createLeague()"
          >
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >League Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Homegrown, ECNL, MLS Next..."
              />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Description</label
              >
              <textarea
                v-model="formData.description"
                rows="3"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Description of the league..."
              ></textarea>
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Sport Type</label
              >
              <select
                v-model="formData.sport_type"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="soccer">Soccer (11v11)</option>
                <option value="futsal">Futsal (5v5)</option>
              </select>
            </div>

            <div class="mb-4">
              <label class="flex items-center">
                <input
                  v-model="formData.is_active"
                  type="checkbox"
                  class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span class="ml-2 text-sm text-gray-700">Active League</span>
              </label>
              <p class="mt-1 text-xs text-gray-500">
                Inactive leagues won't be available for selection
              </p>
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
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'AdminLeagues',
  setup() {
    const authStore = useAuthStore();
    const leagues = ref([]);
    const divisions = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const editingLeague = ref(null);

    const formData = ref({
      name: '',
      description: '',
      sport_type: 'soccer',
      is_active: true,
    });

    const fetchLeagues = async () => {
      try {
        loading.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues`,
          {
            method: 'GET',
          }
        );
        leagues.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchDivisions = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/divisions`,
          {
            method: 'GET',
          }
        );
        divisions.value = response;
      } catch (err) {
        console.error('Error fetching divisions:', err);
      }
    };

    const getDivisionCount = leagueId => {
      return divisions.value.filter(division => division.league_id === leagueId)
        .length;
    };

    const formatDate = dateString => {
      return new Date(dateString).toLocaleDateString();
    };

    const createLeague = async () => {
      try {
        formLoading.value = true;
        error.value = null;

        console.log('Creating league with data:', formData.value);

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues`,
          {
            method: 'POST',
            body: JSON.stringify(formData.value),
          }
        );

        console.log('League created successfully:', response);

        await fetchLeagues();
        closeModals();
        resetForm();
      } catch (err) {
        console.error('Error creating league:', err);
        error.value = err.message || 'Failed to create league';
      } finally {
        formLoading.value = false;
      }
    };

    const editLeague = league => {
      editingLeague.value = league;
      formData.value = { ...league };
      showEditModal.value = true;
    };

    const updateLeague = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues/${editingLeague.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(formData.value),
          }
        );

        await fetchLeagues();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const deleteLeague = async league => {
      if (getDivisionCount(league.id) > 0) {
        error.value =
          'Cannot delete league with existing divisions. Delete divisions first.';
        return;
      }

      if (!confirm(`Are you sure you want to delete "${league.name}"?`)) return;

      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues/${league.id}`,
          {
            method: 'DELETE',
          }
        );

        await fetchLeagues();
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      editingLeague.value = null;
      resetForm();
    };

    const resetForm = () => {
      formData.value = {
        name: '',
        description: '',
        sport_type: 'soccer',
        is_active: true,
      };
    };

    onMounted(async () => {
      await Promise.all([fetchLeagues(), fetchDivisions()]);
    });

    return {
      leagues,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      formData,
      getDivisionCount,
      formatDate,
      createLeague,
      editLeague,
      updateLeague,
      deleteLeague,
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
