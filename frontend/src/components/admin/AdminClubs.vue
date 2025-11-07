<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Clubs Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Club
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

    <!-- Clubs Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="club in clubs"
        :key="club.id"
        class="bg-white shadow-md rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
      >
        <!-- Club Header -->
        <div class="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4">
          <h4 class="text-xl font-bold text-white">{{ club.name }}</h4>
          <p class="text-blue-100 text-sm">{{ club.city }}</p>
        </div>

        <!-- Club Body -->
        <div class="px-6 py-4">
          <div class="mb-4">
            <div
              class="flex items-center justify-between text-sm text-gray-600 mb-2"
            >
              <span class="font-medium">Teams:</span>
              <span
                class="bg-blue-100 text-blue-800 px-2 py-1 rounded-full font-semibold"
              >
                {{ club.team_count }}
              </span>
            </div>
          </div>

          <!-- Teams List -->
          <div v-if="club.teams && club.teams.length > 0" class="space-y-2">
            <div
              class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
            >
              Teams in this club:
            </div>
            <div
              v-for="team in club.teams"
              :key="team.id"
              class="text-sm text-gray-700 pl-2 py-2 hover:bg-gray-50 rounded border-b border-gray-100 last:border-0"
            >
              <div class="flex items-center mb-1">
                <svg
                  class="w-3 h-3 mr-2 text-gray-400 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"
                  />
                </svg>
                <span class="font-medium">{{ team.name }}</span>
              </div>
              <div class="ml-5 flex flex-wrap gap-1">
                <!-- Show league badge based on academy_team flag -->
                <span
                  v-if="team.academy_team"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
                >
                  Academy
                </span>
                <span
                  v-else
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800"
                >
                  Homegrown
                </span>

                <!-- Show additional divisions/leagues if team has mappings -->
                <span
                  v-for="mapping in team.team_mappings || []"
                  :key="`${mapping.age_group_id}-${mapping.division_id}`"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                >
                  {{ mapping.divisions?.leagues?.name || 'Unknown' }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="text-sm text-gray-500 italic">
            No teams in this club yet
          </div>
        </div>

        <!-- Club Footer -->
        <div class="bg-gray-50 px-6 py-3 flex justify-end space-x-2">
          <button
            @click="viewClubDetails(club)"
            class="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            View Details
          </button>
          <button
            @click="deleteClub(club)"
            class="text-red-600 hover:text-red-800 text-sm font-medium"
          >
            Delete
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="!loading && clubs.length === 0"
      class="text-center py-12 bg-gray-50 rounded-lg"
    >
      <svg
        class="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
        />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">No clubs</h3>
      <p class="mt-1 text-sm text-gray-500">
        Get started by creating a new club.
      </p>
      <div class="mt-6">
        <button
          @click="showAddModal = true"
          class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
        >
          Add Club
        </button>
      </div>
    </div>

    <!-- Add Club Modal -->
    <div
      v-if="showAddModal"
      class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-medium text-gray-900">Add Club</h3>
        </div>

        <form @submit.prevent="createClub" class="px-6 py-4 space-y-4">
          <!-- Error Display Inside Modal -->
          <div
            v-if="error"
            class="bg-red-50 border border-red-200 rounded-md p-4"
          >
            <div class="text-red-800">{{ error }}</div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Club Name *
            </label>
            <input
              v-model="newClub.name"
              type="text"
              required
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., IFA"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              City *
            </label>
            <input
              v-model="newClub.city"
              type="text"
              required
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., Weymouth, MA"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Website
            </label>
            <input
              v-model="newClub.website"
              type="url"
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., https://ifasoccer.com"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              v-model="newClub.description"
              rows="3"
              class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="Brief description of the club"
            ></textarea>
          </div>

          <div class="bg-blue-50 border border-blue-200 rounded-md p-3">
            <p class="text-sm text-blue-800">
              <strong>Note:</strong> After creating a club, you can link teams
              to it in the Teams Management section.
            </p>
          </div>

          <div class="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              @click="cancelAdd"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {{ saving ? 'Creating...' : 'Create Club' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';

export default {
  name: 'AdminClubs',
  setup() {
    const authStore = useAuthStore();
    const clubs = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const showAddModal = ref(false);
    const saving = ref(false);

    const newClub = ref({
      name: '',
      city: '',
      website: '',
      description: '',
    });

    const fetchClubs = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/clubs`
        );
        clubs.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching clubs:', err);
        error.value = err.message || 'Failed to load clubs';
      } finally {
        loading.value = false;
      }
    };

    const createClub = async () => {
      if (!newClub.value.name || !newClub.value.city) {
        return;
      }

      saving.value = true;
      error.value = null;

      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/clubs`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(newClub.value),
          }
        );

        // Success! Refresh clubs list
        await fetchClubs();

        // Reset form and close modal only on success
        newClub.value = { name: '', city: '', website: '', description: '' };
        showAddModal.value = false;
        error.value = null; // Clear any previous errors
      } catch (err) {
        console.error('Error creating club:', err);
        error.value = err.message || 'Failed to create club';
        // Don't close modal on error - user needs to see the error and retry
      } finally {
        saving.value = false;
      }
    };

    const viewClubDetails = club => {
      // TODO: Implement club details view
      alert(
        `View details for ${club.name}\n\nChild Teams: ${club.team_count}\nCity: ${club.city}`
      );
    };

    const deleteClub = async club => {
      if (
        !confirm(
          `Are you sure you want to delete "${club.name}"?\n\nThis will only delete the club. Teams will become independent teams.`
        )
      ) {
        return;
      }

      try {
        await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/clubs/${club.id}`,
          {
            method: 'DELETE',
          }
        );

        // Refresh clubs list
        await fetchClubs();
      } catch (err) {
        console.error('Error deleting club:', err);
        error.value = err.message || 'Failed to delete club';
      }
    };

    const cancelAdd = () => {
      newClub.value = { name: '', city: '', website: '', description: '' };
      showAddModal.value = false;
    };

    onMounted(() => {
      fetchClubs();
    });

    return {
      clubs,
      loading,
      error,
      showAddModal,
      newClub,
      saving,
      createClub,
      viewClubDetails,
      deleteClub,
      cancelAdd,
    };
  },
};
</script>
