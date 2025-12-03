<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Teams Management</h3>
      <button
        @click="showAddModal = true"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Team
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

    <!-- Teams Table -->
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
              Parent Club
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              League
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Age Groups
            </th>
            <th
              class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="team in teams" :key="team.id">
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ team.name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                v-if="team.parent_club"
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
              >
                {{ team.parent_club.name }}
              </span>
              <span v-else class="text-gray-400 italic">Independent</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <span
                v-if="team.league_name === 'Academy'"
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800"
              >
                Academy
              </span>
              <span
                v-else-if="team.league_name === 'Homegrown'"
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800"
              >
                Homegrown
              </span>
              <span
                v-else
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800"
              >
                {{ team.league_name || 'Unknown' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="ageGroup in (team.age_groups || []).filter(ag => ag)"
                  :key="ageGroup.id"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                >
                  {{ ageGroup.name }}
                </span>
              </div>
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
            >
              <button
                @click="editTeam(team)"
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button
                @click="manageTeamMappings(team)"
                class="text-green-600 hover:text-green-900 mr-3"
              >
                Leagues
              </button>
              <button
                @click="deleteTeam(team)"
                class="text-red-600 hover:text-red-900"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add/Edit Team Modal -->
    <div
      v-if="showAddModal || showEditModal"
      class="modal-overlay"
      @click="closeModals"
    >
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            {{ showEditModal ? 'Edit Team' : 'Add New Team' }}
          </h3>

          <form @submit.prevent="showEditModal ? updateTeam() : createTeam()">
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Team Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., New York City FC, Boston United..."
              />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >City</label
              >
              <input
                v-model="formData.city"
                type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., New York, Boston..."
              />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Parent Club</label
              >
              <select
                v-model="formData.parentClubId"
                :disabled="isClubManager()"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              >
                <option v-if="!isClubManager()" :value="null">
                  Independent Team (No Parent Club)
                </option>
                <option v-for="club in clubs" :key="club.id" :value="club.id">
                  {{ club.name }}
                </option>
              </select>
              <p class="text-xs text-gray-500 mt-1">
                <span v-if="isClubManager()">
                  Teams you create will be assigned to your club
                </span>
                <span v-else>
                  Link this team to a parent club organization
                </span>
              </p>
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Team Type</label
              >
              <select
                v-model="formData.teamType"
                @change="onTeamTypeChange"
                :required="!showEditModal"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select Team Type</option>
                <option value="league">League Team</option>
                <option value="guest">Guest Team</option>
                <option value="tournament">Tournament Team</option>
              </select>
              <p class="text-xs text-gray-500 mt-1">
                League teams can play in all game types. Guest teams are for
                friendlies only. Tournament teams can play in tournaments and
                friendlies.
              </p>
            </div>

            <div v-if="showEditModal" class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Current Age Groups</label
              >
              <div class="flex flex-wrap gap-1 mb-2">
                <span
                  v-for="ageGroup in editingTeam?.age_groups || []"
                  :key="ageGroup.id"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                >
                  {{ ageGroup.name }}
                </span>
                <span
                  v-if="!editingTeam?.age_groups?.length"
                  class="text-sm text-gray-500 italic"
                >
                  No age groups assigned
                </span>
              </div>
              <p class="text-xs text-gray-500">
                Use the "Leagues" button to manage age group assignments
              </p>
            </div>

            <div v-if="!showEditModal" class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Age Groups</label
              >
              <div
                class="space-y-2 max-h-40 overflow-y-auto border border-gray-300 rounded-md p-3"
              >
                <label
                  v-for="ageGroup in ageGroups"
                  :key="ageGroup.id"
                  class="flex items-center text-sm"
                >
                  <input
                    type="checkbox"
                    :value="ageGroup.id"
                    v-model="formData.ageGroupIds"
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span class="ml-2">{{ ageGroup.name }}</span>
                </label>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                Select one or more age groups this team will participate in
              </p>
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Game Types Participation
                <span v-if="!showEditModal" class="text-xs text-gray-500"
                  >(auto-selected based on team type)</span
                >
              </label>
              <div class="space-y-2">
                <label
                  v-for="gameType in gameTypes"
                  :key="gameType.id"
                  class="flex items-center text-sm"
                >
                  <input
                    type="checkbox"
                    :value="gameType.id"
                    v-model="formData.gameTypeIds"
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span class="ml-2">{{ gameType.name }}</span>
                </label>
              </div>
              <p v-if="showEditModal" class="text-xs text-gray-500 mt-1">
                Note: This will update game type participation for all age
                groups this team is assigned to
              </p>
            </div>

            <div class="mb-4">
              <label
                class="flex items-center text-sm font-medium text-gray-700"
              >
                <input
                  type="checkbox"
                  v-model="formData.academyTeam"
                  class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-2"
                />
                Pro Academy Team
              </label>
              <p class="text-xs text-gray-500 mt-1">
                Check this if this is a pro academy team
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

    <!-- Team Mappings Modal -->
    <div
      v-if="showMappingsModal"
      class="modal-overlay"
      @click="closeMappingsModal"
    >
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            Manage League Assignments - {{ selectedTeam?.name }}
          </h3>

          <div class="mb-4">
            <p class="text-sm text-gray-600 mb-4">
              Assign this team to age groups and divisions. Each assignment
              creates a league participation.
            </p>

            <!-- Current Mappings -->
            <div class="mb-6">
              <h4 class="text-sm font-medium text-gray-700 mb-2">
                Current Assignments
              </h4>
              <div class="space-y-2">
                <div
                  v-for="mapping in selectedTeam?.team_mappings"
                  :key="`${mapping.age_groups.id}-${mapping.divisions.id}`"
                  class="flex items-center justify-between p-3 border border-gray-200 rounded-md"
                >
                  <span class="text-sm">
                    <span class="font-medium">{{
                      mapping.divisions?.leagues?.name || 'Unknown League'
                    }}</span>
                    <span class="text-gray-400 mx-1">/</span>
                    {{ mapping.divisions.name }}
                    <span class="text-gray-400 mx-1">/</span>
                    {{ mapping.age_groups.name }}
                  </span>
                  <button
                    @click="removeTeamMapping(mapping)"
                    class="text-red-600 hover:text-red-900 text-sm"
                  >
                    Remove
                  </button>
                </div>
                <div
                  v-if="!selectedTeam?.team_mappings?.length"
                  class="text-sm text-gray-500 italic"
                >
                  No league assignments yet
                </div>
              </div>
            </div>

            <!-- Add New Mapping -->
            <div class="border-t pt-4">
              <h4 class="text-sm font-medium text-gray-700 mb-3">
                Add New Assignment
              </h4>
              <form @submit.prevent="addTeamMapping()" class="space-y-3">
                <div class="grid grid-cols-3 gap-3">
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1"
                      >League</label
                    >
                    <select
                      v-model="mappingForm.league_id"
                      required
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select League</option>
                      <option
                        v-for="league in leagues"
                        :key="league.id"
                        :value="league.id"
                      >
                        {{ league.name }}
                      </option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1"
                      >Division</label
                    >
                    <select
                      v-model="mappingForm.division_id"
                      required
                      :disabled="!mappingForm.league_id"
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                    >
                      <option value="">
                        {{
                          mappingForm.league_id
                            ? 'Select Division'
                            : 'Select League first'
                        }}
                      </option>
                      <option
                        v-for="division in filteredDivisions"
                        :key="division.id"
                        :value="division.id"
                      >
                        {{ division.name }}
                      </option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1"
                      >Age Group</label
                    >
                    <select
                      v-model="mappingForm.age_group_id"
                      required
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select Age Group</option>
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
                <button
                  type="submit"
                  :disabled="mappingLoading"
                  class="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50"
                >
                  {{ mappingLoading ? 'Adding...' : 'Add Assignment' }}
                </button>
              </form>
            </div>
          </div>

          <div class="flex justify-end">
            <button
              @click="closeMappingsModal"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Close
            </button>
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

export default {
  name: 'AdminTeams',
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const clubs = ref([]);
    const ageGroups = ref([]);
    const divisions = ref([]);
    const leagues = ref([]);
    const gameTypes = ref([]);
    const loading = ref(true);
    const formLoading = ref(false);
    const mappingLoading = ref(false);
    const error = ref(null);
    const showAddModal = ref(false);
    const showEditModal = ref(false);
    const showMappingsModal = ref(false);
    const editingTeam = ref(null);
    const selectedTeam = ref(null);

    const formData = ref({
      name: '',
      city: '',
      parentClubId: null,
      teamType: '',
      ageGroupIds: [],
      gameTypeIds: [],
      academyTeam: false,
    });

    const mappingForm = ref({
      league_id: '',
      age_group_id: '',
      division_id: '',
    });

    // Computed property to filter divisions by selected league
    const filteredDivisions = computed(() => {
      if (!mappingForm.value.league_id) {
        return [];
      }
      return divisions.value.filter(
        d => d.league_id === parseInt(mappingForm.value.league_id)
      );
    });

    const fetchTeams = async () => {
      try {
        loading.value = true;
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams?include_parent=true`,
          {
            method: 'GET',
          }
        );
        teams.value = response;
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchAgeGroups = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/age-groups`,
          {
            method: 'GET',
          }
        );
        ageGroups.value = response;
      } catch (err) {
        console.error('Error fetching age groups:', err);
      }
    };

    const fetchClubs = async () => {
      try {
        // Club managers can only see their own club
        const userRole = authStore.userRole.value;
        const userClubId = authStore.userClubId.value;

        if (userRole === 'club_manager' && userClubId) {
          // Fetch only the club manager's club
          const response = await authStore.apiRequest(
            `${getApiBaseUrl()}/api/clubs/${userClubId}`,
            {
              method: 'GET',
            }
          );
          clubs.value = [response];
          // Auto-select the club for club managers
          formData.value.parentClubId = userClubId;
        } else {
          // Admins can see all clubs
          const response = await authStore.apiRequest(
            `${getApiBaseUrl()}/api/clubs?include_empty=true`,
            {
              method: 'GET',
            }
          );
          clubs.value = response.sort((a, b) => a.name.localeCompare(b.name));
        }
      } catch (err) {
        console.error('Error fetching clubs:', err);
        // Not fatal - parent club is optional
      }
    };

    // Check if user is a club manager (used for UI restrictions)
    const isClubManager = () => {
      return authStore.userRole.value === 'club_manager';
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

    const fetchLeagues = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues`,
          {
            method: 'GET',
          }
        );
        leagues.value = response;
      } catch (err) {
        console.error('Error fetching leagues:', err);
      }
    };

    const fetchGameTypes = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/match-types`,
          {
            method: 'GET',
          }
        );
        gameTypes.value = response;
      } catch (err) {
        console.error('Error fetching game types:', err);
      }
    };

    const onTeamTypeChange = () => {
      // Auto-select game types based on team type
      const teamType = formData.value.teamType;
      const leagueId = gameTypes.value.find(gt => gt.name === 'League')?.id;
      const friendlyId = gameTypes.value.find(gt => gt.name === 'Friendly')?.id;
      const tournamentId = gameTypes.value.find(
        gt => gt.name === 'Tournament'
      )?.id;
      const playoffId = gameTypes.value.find(gt => gt.name === 'Playoff')?.id;

      if (teamType === 'league') {
        // League teams can participate in all game types
        formData.value.gameTypeIds = [
          leagueId,
          friendlyId,
          tournamentId,
          playoffId,
        ].filter(id => id);
      } else if (teamType === 'guest') {
        // Guest teams typically only for friendlies
        formData.value.gameTypeIds = [friendlyId].filter(id => id);
      } else if (teamType === 'tournament') {
        // Tournament teams for tournaments and friendlies
        formData.value.gameTypeIds = [tournamentId, friendlyId].filter(
          id => id
        );
      } else {
        formData.value.gameTypeIds = [];
      }
    };

    const createTeam = async () => {
      try {
        formLoading.value = true;

        // Clear any previous errors
        error.value = null;

        // Validate that at least one age group is selected
        if (
          !formData.value.ageGroupIds ||
          formData.value.ageGroupIds.length === 0
        ) {
          error.value = 'Please select at least one age group';
          return;
        }

        // Create the team with basic info and age groups
        const teamData = {
          name: formData.value.name,
          city: formData.value.city,
          club_id: formData.value.parentClubId,
          age_group_ids: formData.value.ageGroupIds.map(id => parseInt(id)),
          division_id: 1, // Default division - TODO: add division selection to form
          academy_team: formData.value.academyTeam,
        };

        await authStore.apiRequest(`${getApiBaseUrl()}/api/teams`, {
          method: 'POST',
          body: JSON.stringify(teamData),
        });

        // Note: In a full implementation, you would also add game type participation here
        // using the team ID returned from the response and the selected game type IDs

        await fetchTeams();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const editTeam = team => {
      editingTeam.value = team;

      // Determine team type based on current game type participation
      let teamType = 'league'; // default
      const teamGameTypes = team.team_game_types || [];
      const hasLeague = teamGameTypes.some(tgt => tgt.game_type_id === 1);
      const hasTournament = teamGameTypes.some(tgt => tgt.game_type_id === 2);
      const hasFriendly = teamGameTypes.some(tgt => tgt.game_type_id === 3);
      const hasPlayoff = teamGameTypes.some(tgt => tgt.game_type_id === 4);

      if (!hasLeague && !hasTournament && !hasPlayoff && hasFriendly) {
        teamType = 'guest';
      } else if (!hasLeague && hasTournament && hasFriendly && !hasPlayoff) {
        teamType = 'tournament';
      }

      // Get unique game type IDs from all age groups
      const gameTypeIds = [
        ...new Set(teamGameTypes.map(tgt => tgt.game_type_id)),
      ];

      formData.value = {
        name: team.name,
        city: team.city,
        parentClubId: team.club_id || null,
        teamType: teamType,
        ageGroupIds: (team.age_groups || []).map(ag => ag.id),
        gameTypeIds: gameTypeIds,
        academyTeam: team.academy_team || false,
      };
      showEditModal.value = true;
    };

    const updateTeam = async () => {
      try {
        formLoading.value = true;
        const updateData = {
          name: formData.value.name,
          city: formData.value.city,
          club_id: formData.value.parentClubId,
          academy_team: formData.value.academyTeam,
        };
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${editingTeam.value.id}`,
          {
            method: 'PUT',
            body: JSON.stringify(updateData),
          }
        );

        // Update game type participations if changed
        const currentGameTypes = editingTeam.value.team_game_types || [];
        const currentGameTypeIds = [
          ...new Set(currentGameTypes.map(tgt => tgt.game_type_id)),
        ];
        const newGameTypeIds = formData.value.gameTypeIds;

        // Remove game types that are no longer selected
        for (const gameTypeId of currentGameTypeIds) {
          if (!newGameTypeIds.includes(gameTypeId)) {
            // Remove for all age groups
            for (const ageGroup of editingTeam.value.age_groups || []) {
              try {
                await authStore.apiRequest(
                  `${getApiBaseUrl()}/api/teams/${editingTeam.value.id}/game-types/${gameTypeId}/${ageGroup.id}`,
                  {
                    method: 'DELETE',
                  }
                );
              } catch (err) {
                console.error(
                  `Failed to remove game type ${gameTypeId} for age group ${ageGroup.id}:`,
                  err
                );
              }
            }
          }
        }

        // Add new game types
        for (const gameTypeId of newGameTypeIds) {
          if (!currentGameTypeIds.includes(gameTypeId)) {
            // Add for all age groups
            for (const ageGroup of editingTeam.value.age_groups || []) {
              try {
                await authStore.apiRequest(
                  `${getApiBaseUrl()}/api/teams/${editingTeam.value.id}/game-types`,
                  {
                    method: 'POST',
                    body: JSON.stringify({
                      game_type_id: gameTypeId,
                      age_group_id: ageGroup.id,
                    }),
                  }
                );
              } catch (err) {
                console.error(
                  `Failed to add game type ${gameTypeId} for age group ${ageGroup.id}:`,
                  err
                );
              }
            }
          }
        }

        await fetchTeams();
        closeModals();
        resetForm();
      } catch (err) {
        error.value = err.message;
      } finally {
        formLoading.value = false;
      }
    };

    const deleteTeam = async team => {
      if (!confirm(`Are you sure you want to delete "${team.name}"?`)) return;

      try {
        await authStore.apiRequest(`${getApiBaseUrl()}/api/teams/${team.id}`, {
          method: 'DELETE',
        });

        await fetchTeams();
      } catch (err) {
        error.value = err.message;
      }
    };

    const manageTeamMappings = team => {
      selectedTeam.value = team;
      showMappingsModal.value = true;
    };

    const addTeamMapping = async () => {
      try {
        mappingLoading.value = true;
        await authStore.apiRequest(`${getApiBaseUrl()}/api/team-mappings`, {
          method: 'POST',
          body: JSON.stringify({
            team_id: selectedTeam.value.id,
            age_group_id: parseInt(mappingForm.value.age_group_id),
            division_id: parseInt(mappingForm.value.division_id),
          }),
        });

        await fetchTeams();
        selectedTeam.value = teams.value.find(
          t => t.id === selectedTeam.value.id
        );
        mappingForm.value = {
          league_id: '',
          age_group_id: '',
          division_id: '',
        };
      } catch (err) {
        error.value = err.message;
      } finally {
        mappingLoading.value = false;
      }
    };

    const removeTeamMapping = async mapping => {
      if (!confirm('Are you sure you want to remove this league assignment?'))
        return;

      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/team-mappings/${selectedTeam.value.id}/${mapping.age_groups.id}/${mapping.divisions.id}`,
          {
            method: 'DELETE',
          }
        );

        await fetchTeams();
        selectedTeam.value = teams.value.find(
          t => t.id === selectedTeam.value.id
        );
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeModals = () => {
      showAddModal.value = false;
      showEditModal.value = false;
      editingTeam.value = null;
      resetForm();
    };

    const closeMappingsModal = () => {
      showMappingsModal.value = false;
      selectedTeam.value = null;
      mappingForm.value = { league_id: '', age_group_id: '', division_id: '' };
    };

    const resetForm = () => {
      formData.value = {
        name: '',
        city: '',
        parentClubId: null,
        teamType: '',
        ageGroupIds: [],
        gameTypeIds: [],
        academyTeam: false,
      };
    };

    onMounted(async () => {
      // Fetch teams with game counts (optimized backend aggregation)
      // Other reference data (clubs, age groups, etc.) loaded in parallel
      await Promise.all([
        fetchTeams(), // Now includes game_count for each team
        fetchClubs(),
        fetchAgeGroups(),
        fetchDivisions(),
        fetchLeagues(),
        fetchGameTypes(),
      ]);
    });

    return {
      teams,
      clubs,
      ageGroups,
      divisions,
      leagues,
      filteredDivisions,
      gameTypes,
      loading,
      formLoading,
      mappingLoading,
      error,
      showAddModal,
      showEditModal,
      showMappingsModal,
      selectedTeam,
      editingTeam,
      formData,
      mappingForm,
      onTeamTypeChange,
      createTeam,
      editTeam,
      updateTeam,
      deleteTeam,
      manageTeamMappings,
      addTeamMapping,
      removeTeamMapping,
      closeModals,
      closeMappingsModal,
      isClubManager,
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
