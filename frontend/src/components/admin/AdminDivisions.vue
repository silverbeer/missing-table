<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Divisions Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Division
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

    <!-- Divisions Table -->
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
              Teams Count
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
          <tr v-for="division in divisions" :key="division.id">
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ division.name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ division.description }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ getTeamCount(division.id) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(division.created_at) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                @click="editDivision(division)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteDivision(division)"
                class="text-red-600 hover:text-red-900"
                :disabled="getTeamCount(division.id) > 0"
                :class="{
                  'opacity-50 cursor-not-allowed':
                    getTeamCount(division.id) > 0,
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
            {{ showEditModal ? 'Edit Division' : 'Add New Division' }}
          </h3>

          <form
            @submit.prevent="
              showEditModal ? updateDivision() : createDivision()
            "
          >
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Division Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Northeast, Southeast, Central..."
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
                placeholder="Description of the division..."
              ></textarea>
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
  name: 'AdminDivisions',
  setup() {
    const authStore = useAuthStore();
    const divisions = ref([]);
    const teams = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const editingDivision = ref(null);

    const formData = ref({
      name: '',
      description: '',
    });

    const fetchDivisions = async () => {
      try {
        loading.value = true;
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions`,
          {
            method: 'GET',
          }
        );
        divisions.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchTeams = async () => {
      try {
        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`,
          {
            method: 'GET',
          }
        );
        teams.value = response;
      } catch (err) {
        console.error('Error fetching teams:', err);
      }
    };

    const getTeamCount = divisionId => {
      return teams.value.filter(team =>
        team.team_mappings?.some(
          mapping => mapping.divisions?.id === divisionId
        )
      ).length;
    };

    const formatDate = dateString => {
      return new Date(dateString).toLocaleDateString();
    };

    const createDivision = async () => {
      try {
        formLoading.value = true;
        error.value = null; // Clear previous errors

        console.log('Creating division with data:', formData.value);
        console.log('Auth headers:', authStore.getAuthHeaders());
        console.log('User role:', authStore.userRole.value);

        const response = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions`,
          {
            method: 'POST',
            body: JSON.stringify(formData.value),
          }
        );

        console.log('Division created successfully:', response);

        await fetchDivisions();
        closeModals();
        resetForm();
      } catch (err) {
        console.error('Error creating division:', err);
        error.value = err.message || 'Failed to create division';
      } finally {
        formLoading.value = false;
      }
    };

    const editDivision = division => {
      editingDivision.value = division;
      formData.value = { ...division };
      showEditModal.value = true;
    };

    const updateDivision = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions/${editingDivision.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(formData.value),
          }
        );

        await fetchDivisions();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const deleteDivision = async division => {
      if (getTeamCount(division.id) > 0) {
        error.value = 'Cannot delete division with associated teams';
        return;
      }

      if (!confirm(`Are you sure you want to delete "${division.name}"?`))
        return;

      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions/${division.id}`,
          {
            method: 'DELETE',
          }
        );

        await fetchDivisions();
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      editingDivision.value = null;
      resetForm();
    };

    const resetForm = () => {
      formData.value = {
        name: '',
        description: '',
      };
    };

    onMounted(async () => {
      await Promise.all([fetchDivisions(), fetchTeams()]);
    });

    return {
      divisions,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      formData,
      getTeamCount,
      formatDate,
      createDivision,
      editDivision,
      updateDivision,
      deleteDivision,
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
