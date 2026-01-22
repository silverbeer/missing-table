<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Players Management</h3>
    </div>

    <!-- Search and Filters -->
    <div class="mb-6 flex flex-wrap gap-4">
      <div class="flex-1 min-w-[200px]">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search by name or email..."
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          @input="debouncedSearch"
        />
      </div>
      <div class="w-48">
        <select
          v-model="selectedClubId"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          @change="fetchPlayers"
        >
          <option :value="null">All Clubs</option>
          <option v-for="club in clubs" :key="club.id" :value="club.id">
            {{ club.name }}
          </option>
        </select>
      </div>
      <div class="w-48">
        <select
          v-model="selectedTeamId"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          @change="fetchPlayers"
        >
          <option :value="null">All Teams</option>
          <option v-for="team in filteredTeams" :key="team.id" :value="team.id">
            {{ team.name }}
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

    <!-- Players Table -->
    <div
      v-else-if="!loading"
      class="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg"
    >
      <table class="min-w-full divide-y divide-gray-300">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Player
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Email
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Jersey #
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Current Teams
            </th>
            <th
              class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="player in players" :key="player.id">
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="flex items-center">
                <div
                  class="h-10 w-10 flex-shrink-0 rounded-full bg-gray-200 flex items-center justify-center"
                >
                  <img
                    v-if="player.photo_1_url"
                    :src="player.photo_1_url"
                    class="h-10 w-10 rounded-full object-cover"
                    alt=""
                  />
                  <span v-else class="text-gray-500 text-sm">{{
                    getInitials(player.display_name)
                  }}</span>
                </div>
                <div class="ml-4">
                  <div class="text-sm font-medium text-gray-900">
                    {{ player.display_name || 'Unknown' }}
                  </div>
                </div>
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ player.email || '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ player.player_number || '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="assignment in player.current_teams"
                  :key="assignment.id"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                >
                  {{ assignment.team?.name || 'Unknown Team' }}
                </span>
                <span
                  v-if="
                    !player.current_teams || player.current_teams.length === 0
                  "
                  class="text-gray-400 italic"
                >
                  No team assigned
                </span>
              </div>
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                @click="openEditModal(player)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="openTeamsModal(player)"
                class="text-green-600 hover:text-green-900"
              >
                Teams
              </button>
            </td>
          </tr>
          <tr v-if="players.length === 0">
            <td colspan="5" class="px-6 py-8 text-center text-gray-500">
              No players found
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div
        v-if="totalCount > 0"
        class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6"
      >
        <div class="flex-1 flex justify-between sm:hidden">
          <button
            @click="previousPage"
            :disabled="offset === 0"
            class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            @click="nextPage"
            :disabled="offset + limit >= totalCount"
            class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
        <div
          class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between"
        >
          <div>
            <p class="text-sm text-gray-700">
              Showing
              <span class="font-medium">{{ offset + 1 }}</span>
              to
              <span class="font-medium">{{
                Math.min(offset + limit, totalCount)
              }}</span>
              of
              <span class="font-medium">{{ totalCount }}</span>
              results
            </p>
          </div>
          <div>
            <nav
              class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"
              aria-label="Pagination"
            >
              <button
                @click="previousPage"
                :disabled="offset === 0"
                class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                @click="nextPage"
                :disabled="offset + limit >= totalCount"
                class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
              >
                Next
              </button>
            </nav>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Player Modal -->
    <div
      v-if="showEditModal"
      class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50"
      @click="closeModals"
    >
      <div
        class="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white"
        @click.stop
      >
        <div class="mt-3">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Edit Player</h3>
          <form @submit.prevent="updatePlayer">
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Display Name</label
              >
              <input
                v-model="editForm.display_name"
                type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Jersey Number</label
              >
              <input
                v-model.number="editForm.player_number"
                type="number"
                min="1"
                max="99"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Positions</label
              >
              <div class="flex flex-wrap gap-2">
                <label
                  v-for="pos in availablePositions"
                  :key="pos"
                  class="inline-flex items-center"
                >
                  <input
                    type="checkbox"
                    :value="pos"
                    v-model="editForm.positions"
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span class="ml-2 text-sm text-gray-700">{{ pos }}</span>
                </label>
              </div>
            </div>
            <div class="flex justify-end gap-2">
              <button
                type="button"
                @click="closeModals"
                class="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="formLoading"
                class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {{ formLoading ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Manage Teams Modal -->
    <div
      v-if="showTeamsModal"
      class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50"
      @click="closeModals"
    >
      <div
        class="relative top-20 mx-auto p-5 border w-[500px] shadow-lg rounded-md bg-white"
        @click.stop
      >
        <div class="mt-3">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            Manage Teams for {{ selectedPlayer?.display_name }}
          </h3>

          <!-- Current Team Assignments -->
          <div class="mb-6">
            <h4 class="text-sm font-medium text-gray-700 mb-2">
              Current Team Assignments
            </h4>
            <div
              v-if="selectedPlayer?.current_teams?.length > 0"
              class="space-y-2"
            >
              <div
                v-for="assignment in selectedPlayer.current_teams"
                :key="assignment.id"
                class="flex items-center justify-between p-2 bg-gray-50 rounded"
              >
                <div>
                  <span class="font-medium">{{
                    assignment.team?.name || 'Unknown'
                  }}</span>
                  <span class="text-gray-500 text-sm ml-2">
                    ({{ assignment.season?.name || 'Unknown Season' }})
                  </span>
                </div>
                <button
                  @click="endTeamAssignment(assignment)"
                  class="text-red-600 hover:text-red-800 text-sm"
                >
                  End
                </button>
              </div>
            </div>
            <div v-else class="text-gray-500 text-sm">
              No current assignments
            </div>
          </div>

          <!-- Add New Assignment -->
          <div class="border-t pt-4">
            <h4 class="text-sm font-medium text-gray-700 mb-2">
              Add Team Assignment
            </h4>
            <form @submit.prevent="addTeamAssignment">
              <div class="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label class="block text-sm text-gray-600 mb-1">Season</label>
                  <select
                    v-model="assignmentForm.season_id"
                    required
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option :value="null" disabled>Select season</option>
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
                  <label class="block text-sm text-gray-600 mb-1">Team</label>
                  <select
                    v-model="assignmentForm.team_id"
                    required
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option :value="null" disabled>Select team</option>
                    <option
                      v-for="team in teams"
                      :key="team.id"
                      :value="team.id"
                    >
                      {{ team.name }}
                    </option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label class="block text-sm text-gray-600 mb-1"
                    >Jersey Number</label
                  >
                  <input
                    v-model.number="assignmentForm.jersey_number"
                    type="number"
                    min="1"
                    max="99"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div class="flex items-end">
                  <label class="inline-flex items-center">
                    <input
                      type="checkbox"
                      v-model="assignmentForm.is_current"
                      class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span class="ml-2 text-sm text-gray-700">Current team</span>
                  </label>
                </div>
              </div>
              <div class="flex justify-end gap-2">
                <button
                  type="button"
                  @click="closeModals"
                  class="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
                >
                  Close
                </button>
                <button
                  type="submit"
                  :disabled="formLoading"
                  class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {{ formLoading ? 'Adding...' : 'Add Team' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import { POSITION_ABBREVIATIONS } from '@/constants/positions';

export default {
  name: 'AdminPlayers',
  setup() {
    const authStore = useAuthStore();

    // State
    const players = ref([]);
    const clubs = ref([]);
    const teams = ref([]);
    const seasons = ref([]);
    const loading = ref(false);
    const formLoading = ref(false);
    const error = ref(null);
    const searchQuery = ref('');
    const selectedClubId = ref(null);
    const selectedTeamId = ref(null);
    const offset = ref(0);
    const limit = ref(50);
    const totalCount = ref(0);

    // Modal state
    const showEditModal = ref(false);
    const showTeamsModal = ref(false);
    const selectedPlayer = ref(null);

    // Form state
    const editForm = ref({
      display_name: '',
      player_number: null,
      positions: [],
    });

    const assignmentForm = ref({
      team_id: null,
      season_id: null,
      jersey_number: null,
      is_current: true,
    });

    const availablePositions = POSITION_ABBREVIATIONS;

    // Computed
    const filteredTeams = computed(() => {
      if (!selectedClubId.value) return teams.value;
      return teams.value.filter(t => t.club_id === selectedClubId.value);
    });

    // Debounced search
    let searchTimeout = null;
    const debouncedSearch = () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        offset.value = 0;
        fetchPlayers();
      }, 300);
    };

    // API calls
    const fetchPlayers = async () => {
      try {
        loading.value = true;
        error.value = null;

        const params = new URLSearchParams();
        if (searchQuery.value) params.append('search', searchQuery.value);
        if (selectedClubId.value)
          params.append('club_id', selectedClubId.value);
        if (selectedTeamId.value)
          params.append('team_id', selectedTeamId.value);
        params.append('limit', limit.value);
        params.append('offset', offset.value);

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/players?${params.toString()}`,
          { method: 'GET' }
        );

        players.value = response.players || [];
        totalCount.value = response.total || 0;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchClubs = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs?include_empty=true`,
          { method: 'GET' }
        );
        clubs.value = response.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching clubs:', err);
      }
    };

    const fetchTeams = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams`,
          { method: 'GET' }
        );
        teams.value = response.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching teams:', err);
      }
    };

    const fetchSeasons = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons`,
          { method: 'GET' }
        );
        seasons.value = response;
      } catch (err) {
        console.error('Error fetching seasons:', err);
      }
    };

    const updatePlayer = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/players/${selectedPlayer.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify({
              display_name: editForm.value.display_name,
              player_number: editForm.value.player_number,
              positions: editForm.value.positions,
            }),
          }
        );
        await fetchPlayers();
        closeModals();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const addTeamAssignment = async () => {
      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/players/${selectedPlayer.value.id}/teams`,
          {
            method: 'POST',
            body: JSON.stringify({
              team_id: assignmentForm.value.team_id,
              season_id: assignmentForm.value.season_id,
              jersey_number: assignmentForm.value.jersey_number,
              is_current: assignmentForm.value.is_current,
            }),
          }
        );
        // Refresh player data
        await fetchPlayers();
        // Refresh selected player's team assignments
        const updatedPlayer = players.value.find(
          p => p.id === selectedPlayer.value.id
        );
        if (updatedPlayer) {
          selectedPlayer.value = updatedPlayer;
        }
        // Reset form
        assignmentForm.value = {
          team_id: null,
          season_id: null,
          jersey_number: null,
          is_current: true,
        };
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const endTeamAssignment = async assignment => {
      if (!confirm('End this team assignment?')) return;

      try {
        formLoading.value = true;
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/players/teams/${assignment.id}/end`,
          {
            method: 'PUT',
          }
        );
        // Refresh player data
        await fetchPlayers();
        // Refresh selected player's team assignments
        const updatedPlayer = players.value.find(
          p => p.id === selectedPlayer.value.id
        );
        if (updatedPlayer) {
          selectedPlayer.value = updatedPlayer;
        }
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    // Modal helpers
    const openEditModal = player => {
      selectedPlayer.value = player;
      editForm.value = {
        display_name: player.display_name || '',
        player_number: player.player_number || null,
        positions: player.positions || [],
      };
      showEditModal.value = true;
    };

    const openTeamsModal = player => {
      selectedPlayer.value = player;
      assignmentForm.value = {
        team_id: null,
        season_id: null,
        jersey_number: null,
        is_current: true,
      };
      showTeamsModal.value = true;
    };

    const closeModals = () => {
      showEditModal.value = false;
      showTeamsModal.value = false;
      selectedPlayer.value = null;
    };

    // Pagination
    const previousPage = () => {
      if (offset.value > 0) {
        offset.value = Math.max(0, offset.value - limit.value);
        fetchPlayers();
      }
    };

    const nextPage = () => {
      if (offset.value + limit.value < totalCount.value) {
        offset.value += limit.value;
        fetchPlayers();
      }
    };

    // Helpers
    const getInitials = name => {
      if (!name) return '?';
      return name
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    };

    // Lifecycle
    onMounted(() => {
      fetchPlayers();
      fetchClubs();
      fetchTeams();
      fetchSeasons();
    });

    return {
      // State
      players,
      clubs,
      teams,
      seasons,
      loading,
      formLoading,
      error,
      searchQuery,
      selectedClubId,
      selectedTeamId,
      offset,
      limit,
      totalCount,
      showEditModal,
      showTeamsModal,
      selectedPlayer,
      editForm,
      assignmentForm,
      availablePositions,
      filteredTeams,

      // Methods
      fetchPlayers,
      debouncedSearch,
      updatePlayer,
      addTeamAssignment,
      endTeamAssignment,
      openEditModal,
      openTeamsModal,
      closeModals,
      previousPage,
      nextPage,
      getInitials,
    };
  },
};
</script>
