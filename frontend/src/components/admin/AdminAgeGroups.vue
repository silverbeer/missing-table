<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Age Groups Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Age Group
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

    <!-- Age Groups Table -->
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
          <tr v-for="ageGroup in ageGroups" :key="ageGroup.id">
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ ageGroup.name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ getTeamCount(ageGroup.id) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(ageGroup.created_at) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                @click="editAgeGroup(ageGroup)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="deleteAgeGroup(ageGroup)"
                class="text-red-600 hover:text-red-900"
                :disabled="getTeamCount(ageGroup.id) > 0"
                :class="{
                  'opacity-50 cursor-not-allowed':
                    getTeamCount(ageGroup.id) > 0,
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
            {{ showEditModal ? 'Edit Age Group' : 'Add New Age Group' }}
          </h3>

          <form
            @submit.prevent="
              showEditModal ? updateAgeGroup() : createAgeGroup()
            "
          >
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., U13, U14, U15..."
              />
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
  name: 'AdminAgeGroups',
  setup() {
    const authStore = useAuthStore();
    const ageGroups = ref([]);
    const teams = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const error = ref(null);
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const editingAgeGroup = ref(null);

    const formData = ref({
      name: '',
    });

    const fetchAgeGroups = async () => {
      try {
        loading.value = true;
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups`
        );
        if (!response.ok) throw new Error('Failed to fetch age groups');
        ageGroups.value = await response.json();
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchTeams = async () => {
      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`
        );
        if (!response.ok) throw new Error('Failed to fetch teams');
        teams.value = await response.json();
      } catch (err) {
        console.error('Error fetching teams:', err);
      }
    };

    const getTeamCount = ageGroupId => {
      return teams.value.filter(team =>
        team.age_groups.some(ag => ag.id === ageGroupId)
      ).length;
    };

    const formatDate = dateString => {
      return new Date(dateString).toLocaleDateString();
    };

    const createAgeGroup = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups`,
          {
            method: 'POST',
            body: JSON.stringify(formData.value),
          }
        );

        await fetchAgeGroups();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const editAgeGroup = ageGroup => {
      editingAgeGroup.value = ageGroup;
      formData.value = { ...ageGroup };
      showEditModal.value = true;
    };

    const updateAgeGroup = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups/${editingAgeGroup.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(formData.value),
          }
        );

        await fetchAgeGroups();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const deleteAgeGroup = async ageGroup => {
      if (getTeamCount(ageGroup.id) > 0) {
        error.value = 'Cannot delete age group with associated teams';
        return;
      }

      if (!confirm(`Are you sure you want to delete "${ageGroup.name}"?`))
        return;

      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups/${ageGroup.id}`,
          {
            method: 'DELETE',
          }
        );

        await fetchAgeGroups();
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      editingAgeGroup.value = null;
      resetForm();
    };

    const resetForm = () => {
      formData.value = { name: '' };
    };

    onMounted(async () => {
      await Promise.all([fetchAgeGroups(), fetchTeams()]);
    });

    return {
      ageGroups,
      loading,
      formLoading,
      error,
      showAddModal,
      showEditModal,
      formData,
      getTeamCount,
      formatDate,
      createAgeGroup,
      editAgeGroup,
      updateAgeGroup,
      deleteAgeGroup,
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
