<template>
  <div data-testid="admin-teams">
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-fg">Teams Management</h3>
      <button
        @click="showAddModal = true"
        data-testid="add-team-button"
        class="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Team
      </button>
    </div>

    <!-- Search -->
    <div class="mb-4">
      <input
        v-model="teamSearch"
        type="search"
        placeholder="Search teams by name or club…"
        data-testid="team-search"
        class="w-full sm:w-80 bg-card text-fg border border-line rounded-md px-3 py-2 text-sm focus:ring-brand-500 focus:border-brand-500"
      />
    </div>

    <!-- Loading State -->
    <div
      v-if="loading"
      class="flex justify-center py-8"
      data-testid="teams-loading"
    >
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
      ></div>
    </div>

    <!-- Error State -->
    <div
      v-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4 mb-4"
      data-testid="teams-error"
    >
      <div class="text-red-800">{{ error }}</div>
    </div>

    <!-- Teams Table -->
    <div
      v-else
      class="overflow-x-auto shadow ring-1 ring-black ring-opacity-5 md:rounded-lg"
      data-testid="teams-table-container"
    >
      <table class="min-w-full divide-y divide-line" data-testid="teams-table">
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
              Parent Club
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              League
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Age Groups
            </th>
            <th
              class="px-6 py-3 text-right text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-card divide-y divide-line" data-testid="teams-tbody">
          <tr
            v-if="teams.length > 0 && filteredTeams.length === 0"
            data-testid="team-search-empty"
          >
            <td colspan="5" class="px-6 py-8 text-center text-sm text-fg-muted">
              No teams match "{{ teamSearch }}".
            </td>
          </tr>
          <tr
            v-for="team in filteredTeams"
            :key="team.id"
            :data-testid="`team-row-${team.id}`"
            data-team-row
          >
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-fg"
              data-testid="team-name"
            >
              {{ team.name }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted">
              <span
                v-if="team.parent_club"
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-500/15 dark:text-purple-300"
              >
                {{ team.parent_club.name }}
              </span>
              <span v-else class="text-fg-muted italic">Independent</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted">
              <span
                v-if="team.league_name === 'Academy'"
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-500/15 dark:text-purple-300"
              >
                Academy
              </span>
              <span
                v-else-if="team.league_name === 'Homegrown'"
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300"
              >
                Homegrown
              </span>
              <span
                v-else
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-surface-alt dark:text-fg"
              >
                {{ team.league_name || 'Unknown' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="ageGroup in (team.age_groups || []).filter(ag => ag)"
                  :key="ageGroup.id"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-brand-100 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200"
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
                class="text-brand-600 dark:text-brand-300 hover:text-brand-900 mr-3"
                data-testid="edit-team-button"
              >
                Edit
              </button>
              <button
                @click="manageTeamMappings(team)"
                class="text-green-600 hover:text-green-900 mr-3"
                data-testid="manage-leagues-button"
              >
                Leagues
              </button>
              <button
                @click="manageRoster(team)"
                class="text-purple-600 hover:text-purple-900 mr-3"
                data-testid="manage-roster-button"
              >
                Roster
              </button>
              <button
                @click="deleteTeam(team)"
                class="text-red-600 hover:text-red-900"
                data-testid="delete-team-button"
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
      data-testid="team-modal-overlay"
    >
      <div class="modal-content" @click.stop data-testid="team-modal">
        <div class="p-6">
          <h3
            class="text-lg font-medium text-fg mb-4"
            data-testid="team-modal-title"
          >
            {{ showEditModal ? 'Edit Team' : 'Add New Team' }}
          </h3>

          <form
            @submit.prevent="showEditModal ? updateTeam() : createTeam()"
            data-testid="team-form"
          >
            <div class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2"
                >Team Name</label
              >
              <input
                v-model="formData.name"
                type="text"
                required
                data-testid="team-name-input"
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="e.g., New York City FC, Boston United..."
              />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2">City</label>
              <input
                v-model="formData.city"
                type="text"
                data-testid="team-city-input"
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="e.g., New York, Boston..."
              />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2"
                >Parent Club</label
              >
              <select
                v-model="formData.parentClubId"
                :disabled="isClubManager()"
                data-testid="team-club-select"
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-surface-alt disabled:cursor-not-allowed"
              >
                <option v-if="!isClubManager()" :value="null">
                  Independent Team (No Parent Club)
                </option>
                <option v-for="club in clubs" :key="club.id" :value="club.id">
                  {{ club.name }}
                </option>
              </select>
              <p class="text-xs text-fg-muted mt-1">
                <span v-if="isClubManager()">
                  Teams you create will be assigned to your club
                </span>
                <span v-else>
                  Link this team to a parent club organization
                </span>
              </p>
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2"
                >Team Type<span v-if="!showEditModal" class="text-red-500"
                  >*</span
                ></label
              >
              <select
                v-model="formData.teamType"
                @change="onTeamTypeChange"
                :required="!showEditModal"
                data-testid="team-type-select"
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Select Team Type</option>
                <option value="league">League Team</option>
                <option value="guest">Guest Team</option>
                <option value="tournament">Tournament Team</option>
              </select>
              <p class="text-xs text-fg-muted mt-1">
                League teams can play in all game types. Guest teams are for
                friendlies only. Tournament teams can play in tournaments and
                friendlies.
              </p>
            </div>

            <!-- League and Division Selection (only for Add, not Edit) -->
            <div
              v-if="!showEditModal && formData.teamType === 'league'"
              class="mb-4"
            >
              <label class="block text-sm font-medium text-fg mb-2"
                >League <span class="text-red-500">*</span></label
              >
              <select
                v-model="formData.leagueId"
                @change="formData.divisionId = null"
                required
                data-testid="team-league-select"
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option :value="null">Select League</option>
                <option
                  v-for="league in leagues"
                  :key="league.id"
                  :value="league.id"
                >
                  {{ league.name }}
                </option>
              </select>
              <p class="text-xs text-fg-muted mt-1">
                Select which league this team will participate in
              </p>
            </div>

            <div
              v-if="
                !showEditModal &&
                formData.teamType === 'league' &&
                formData.leagueId
              "
              class="mb-4"
            >
              <label class="block text-sm font-medium text-fg mb-2"
                >Division <span class="text-red-500">*</span></label
              >
              <select
                v-model="formData.divisionId"
                required
                data-testid="team-division-select"
                class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option :value="null">Select Division</option>
                <option
                  v-for="division in formFilteredDivisions"
                  :key="division.id"
                  :value="division.id"
                >
                  {{ division.name }}
                </option>
              </select>
              <p class="text-xs text-fg-muted mt-1">
                Select the division within the league (e.g., Northeast, Bracket
                A)
              </p>
            </div>

            <div v-if="showEditModal" class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2"
                >Current Age Groups</label
              >
              <div class="flex flex-wrap gap-1 mb-2">
                <span
                  v-for="ageGroup in editingTeam?.age_groups || []"
                  :key="ageGroup.id"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-brand-100 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200"
                >
                  {{ ageGroup.name }}
                </span>
                <span
                  v-if="!editingTeam?.age_groups?.length"
                  class="text-sm text-fg-muted italic"
                >
                  No age groups assigned
                </span>
              </div>
              <p class="text-xs text-fg-muted">
                Use the "Leagues" button to manage age group assignments
              </p>
            </div>

            <div v-if="!showEditModal" class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2"
                >Age Groups</label
              >
              <div
                class="space-y-2 max-h-40 overflow-y-auto border border-line rounded-md p-3"
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
                    class="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  <span class="ml-2">{{ ageGroup.name }}</span>
                </label>
              </div>
              <p class="text-xs text-fg-muted mt-1">
                Select one or more age groups this team will participate in
              </p>
            </div>

            <!-- Create mode: team-wide game types, applied to every selected
                 age group when the team is created. -->
            <div v-if="!showEditModal" class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2">
                Game Types Participation
                <span class="text-xs text-fg-muted"
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
                    class="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  <span class="ml-2">{{ gameType.name }}</span>
                </label>
              </div>
            </div>

            <!-- Edit mode: per-age-group match-type participation matrix. Each
                 checkbox is one (match type, age group) cell, so participation
                 can be set for a single age group independently. -->
            <div v-else class="mb-4">
              <label class="block text-sm font-medium text-fg mb-2">
                Match Type Participation
              </label>
              <div
                v-if="(editingTeam?.age_groups || []).length"
                class="overflow-x-auto"
              >
                <table class="min-w-full text-sm">
                  <thead>
                    <tr>
                      <th class="text-left font-medium text-fg-muted py-1 pr-3">
                        Age Group
                      </th>
                      <th
                        v-for="gameType in gameTypes"
                        :key="gameType.id"
                        class="text-center font-medium text-fg-muted py-1 px-2"
                      >
                        {{ gameType.name }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="ageGroup in editingTeam.age_groups"
                      :key="ageGroup.id"
                      data-participation-row
                    >
                      <td class="py-1 pr-3 text-fg">{{ ageGroup.name }}</td>
                      <td
                        v-for="gameType in gameTypes"
                        :key="gameType.id"
                        class="text-center py-1 px-2"
                      >
                        <input
                          type="checkbox"
                          :checked="hasParticipation(gameType.id, ageGroup.id)"
                          :data-participation-cell="`${gameType.id}:${ageGroup.id}`"
                          @change="
                            toggleParticipation(gameType.id, ageGroup.id)
                          "
                          class="rounded border-line text-brand-600 focus:ring-brand-500"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="text-xs text-fg-muted">
                Assign an age group first (via the "Leagues" button) to set
                match type participation.
              </p>
              <p class="text-xs text-fg-muted mt-1">
                Enable each match type per age group. Changes apply on Update.
              </p>
            </div>

            <div class="mb-4">
              <label class="flex items-center text-sm font-medium text-fg">
                <input
                  type="checkbox"
                  v-model="formData.academyTeam"
                  class="rounded border-line text-brand-600 focus:ring-brand-500 mr-2"
                />
                Pro Academy Team
              </label>
              <p class="text-xs text-fg-muted mt-1">
                Check this if this is a pro academy team
              </p>
            </div>

            <div class="flex justify-end space-x-3">
              <button
                type="button"
                @click="closeModals"
                data-testid="team-modal-cancel"
                class="px-4 py-2 text-sm font-medium text-fg bg-surface-alt hover:bg-line rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="formLoading"
                data-testid="team-modal-submit"
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

    <!-- Team Mappings Modal -->
    <div
      v-if="showMappingsModal"
      class="modal-overlay"
      @click="closeMappingsModal"
    >
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-fg mb-4">
            Manage League Assignments - {{ selectedTeam?.name }}
          </h3>

          <div class="mb-4">
            <p class="text-sm text-fg-muted mb-4">
              Assign this team to age groups and divisions. Each assignment
              creates a league participation.
            </p>

            <!-- Current Mappings -->
            <div class="mb-6">
              <h4 class="text-sm font-medium text-fg mb-2">
                Current Assignments
              </h4>
              <div class="space-y-2">
                <div
                  v-for="mapping in selectedTeam?.team_mappings"
                  :key="`${mapping.age_groups.id}-${mapping.divisions.id}`"
                  class="flex items-center justify-between p-3 border border-line rounded-md"
                >
                  <span class="text-sm">
                    <span class="font-medium">{{
                      mapping.divisions?.leagues?.name || 'Unknown League'
                    }}</span>
                    <span class="text-fg-muted mx-1">/</span>
                    {{ mapping.divisions.name }}
                    <span class="text-fg-muted mx-1">/</span>
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
                  class="text-sm text-fg-muted italic"
                >
                  No league assignments yet
                </div>
              </div>
            </div>

            <!-- Add New Mapping -->
            <div class="border-t border-line pt-4">
              <h4 class="text-sm font-medium text-fg mb-3">
                Add New Assignment
              </h4>
              <form @submit.prevent="addTeamMapping()" class="space-y-3">
                <div class="grid grid-cols-3 gap-3">
                  <div>
                    <label class="block text-sm font-medium text-fg mb-1"
                      >League</label
                    >
                    <select
                      v-model="mappingForm.league_id"
                      required
                      class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
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
                    <label class="block text-sm font-medium text-fg mb-1"
                      >Division</label
                    >
                    <select
                      v-model="mappingForm.division_id"
                      required
                      :disabled="!mappingForm.league_id"
                      class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-surface-alt disabled:cursor-not-allowed"
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
                    <label class="block text-sm font-medium text-fg mb-1"
                      >Age Group</label
                    >
                    <select
                      v-model="mappingForm.age_group_id"
                      required
                      class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
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
              class="px-4 py-2 text-sm font-medium text-fg bg-surface-alt hover:bg-line rounded-md"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Roster Manager Modal -->
    <RosterManager
      v-if="showRosterModal && selectedTeamForRoster"
      :team-id="selectedTeamForRoster.id"
      :team-name="selectedTeamForRoster.name"
      :season-id="currentSeasonId"
      :team-age-groups="selectedTeamForRoster.age_groups || []"
      @close="closeRosterModal"
    />
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import RosterManager from '@/components/roster/RosterManager.vue';

export default {
  name: 'AdminTeams',
  components: {
    RosterManager,
  },
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const teamSearch = ref('');
    const filteredTeams = computed(() => {
      const q = teamSearch.value.trim().toLowerCase();
      if (!q) return teams.value;
      return teams.value.filter(t => {
        const name = (t.name || '').toLowerCase();
        const club = (t.parent_club?.name || '').toLowerCase();
        return name.includes(q) || club.includes(q);
      });
    });
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
    const showRosterModal = ref(false);
    const editingTeam = ref(null);
    const selectedTeam = ref(null);
    const selectedTeamForRoster = ref(null);
    const seasons = ref([]);
    const currentSeasonId = ref(null);

    const formData = ref({
      name: '',
      city: '',
      parentClubId: null,
      teamType: '',
      ageGroupIds: [],
      gameTypeIds: [],
      academyTeam: false,
      leagueId: null,
      divisionId: null,
    });

    // Per-age-group match-type participation (Edit Team matrix). Keys are
    // `${matchTypeId}:${ageGroupId}` for currently-enabled cells;
    // participationOriginal snapshots the loaded state so updateTeam can diff.
    const participation = ref(new Set());
    const participationOriginal = ref(new Set());

    const partKey = (matchTypeId, ageGroupId) => `${matchTypeId}:${ageGroupId}`;
    const hasParticipation = (matchTypeId, ageGroupId) =>
      participation.value.has(partKey(matchTypeId, ageGroupId));
    const toggleParticipation = (matchTypeId, ageGroupId) => {
      const key = partKey(matchTypeId, ageGroupId);
      const next = new Set(participation.value);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      participation.value = next;
    };

    const mappingForm = ref({
      league_id: '',
      age_group_id: '',
      division_id: '',
    });

    // Computed property to filter divisions by selected league (for mappings modal)
    const filteredDivisions = computed(() => {
      if (!mappingForm.value.league_id) {
        return [];
      }
      return divisions.value.filter(
        d => d.league_id === parseInt(mappingForm.value.league_id)
      );
    });

    // Computed property to filter divisions by selected league (for team creation form)
    const formFilteredDivisions = computed(() => {
      if (!formData.value.leagueId) {
        return [];
      }
      return divisions.value.filter(
        d => d.league_id === parseInt(formData.value.leagueId)
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

    const fetchSeasons = async () => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons`,
          {
            method: 'GET',
          }
        );
        seasons.value = response;
        // Default to the admin-set current season, else the newest (response
        // is ordered newest-first).
        const current = response.find(s => s.is_current) || response[0];
        if (current) {
          currentSeasonId.value = current.id;
        }
      } catch (err) {
        console.error('Error fetching seasons:', err);
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

        // Validate that a division is selected (only for league teams)
        if (
          formData.value.teamType === 'league' &&
          !formData.value.divisionId
        ) {
          error.value = 'Please select a league and division';
          return;
        }

        // Create the team with basic info and age groups
        const teamData = {
          name: formData.value.name,
          city: formData.value.city,
          club_id: formData.value.parentClubId,
          age_group_ids: formData.value.ageGroupIds.map(id => parseInt(id)),
          match_type_ids: formData.value.gameTypeIds.map(id => parseInt(id)),
          division_id: formData.value.divisionId
            ? parseInt(formData.value.divisionId)
            : null,
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

    const editTeam = async team => {
      editingTeam.value = team;

      formData.value = {
        name: team.name,
        city: team.city,
        parentClubId: team.club_id || null,
        teamType: 'league',
        ageGroupIds: (team.age_groups || []).map(ag => ag.id),
        gameTypeIds: [],
        academyTeam: team.academy_team || false,
      };

      // Load current per-age-group match-type participation for the matrix.
      participation.value = new Set();
      participationOriginal.value = new Set();
      try {
        const rows = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${team.id}/match-types`,
          { method: 'GET' }
        );
        const loaded = new Set(
          (rows || []).map(r => partKey(r.match_type_id, r.age_group_id))
        );
        participation.value = loaded;
        participationOriginal.value = new Set(loaded);
      } catch (err) {
        console.error('Failed to load match-type participation:', err);
        error.value = 'Failed to load match-type participation.';
      }

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

        // Diff the per-age-group participation matrix and apply each change
        // via the add/remove match-type endpoints. Each cell is one
        // (match_type, age_group) pair, so we can target a single age group
        // without touching the others. Failures are collected and surfaced
        // rather than silently swallowed.
        const added = [...participation.value].filter(
          key => !participationOriginal.value.has(key)
        );
        const removed = [...participationOriginal.value].filter(
          key => !participation.value.has(key)
        );
        const participationErrors = [];

        for (const key of added) {
          const [matchTypeId, ageGroupId] = key.split(':').map(Number);
          try {
            await authStore.apiRequest(
              `${getApiBaseUrl()}/api/teams/${editingTeam.value.id}/match-types`,
              {
                method: 'POST',
                body: JSON.stringify({
                  match_type_id: matchTypeId,
                  age_group_id: ageGroupId,
                }),
              }
            );
          } catch (err) {
            console.error(
              `Failed to add match type ${matchTypeId} for age group ${ageGroupId}:`,
              err
            );
            participationErrors.push(err);
          }
        }

        for (const key of removed) {
          const [matchTypeId, ageGroupId] = key.split(':').map(Number);
          try {
            await authStore.apiRequest(
              `${getApiBaseUrl()}/api/teams/${editingTeam.value.id}/match-types/${matchTypeId}/${ageGroupId}`,
              {
                method: 'DELETE',
              }
            );
          } catch (err) {
            console.error(
              `Failed to remove match type ${matchTypeId} for age group ${ageGroupId}:`,
              err
            );
            participationErrors.push(err);
          }
        }

        if (participationErrors.length > 0) {
          error.value =
            'Team saved, but some match-type changes failed to apply. Please try again.';
          await fetchTeams();
          return;
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

    const manageRoster = team => {
      selectedTeamForRoster.value = team;
      showRosterModal.value = true;
    };

    const closeRosterModal = () => {
      showRosterModal.value = false;
      selectedTeamForRoster.value = null;
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
        leagueId: null,
        divisionId: null,
      };
      participation.value = new Set();
      participationOriginal.value = new Set();
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
        fetchSeasons(),
      ]);
    });

    return {
      teams,
      teamSearch,
      filteredTeams,
      clubs,
      ageGroups,
      divisions,
      leagues,
      filteredDivisions,
      formFilteredDivisions,
      gameTypes,
      seasons,
      currentSeasonId,
      loading,
      formLoading,
      mappingLoading,
      error,
      showAddModal,
      showEditModal,
      showMappingsModal,
      showRosterModal,
      selectedTeam,
      selectedTeamForRoster,
      editingTeam,
      formData,
      participation,
      participationOriginal,
      hasParticipation,
      toggleParticipation,
      mappingForm,
      onTeamTypeChange,
      createTeam,
      editTeam,
      updateTeam,
      deleteTeam,
      manageTeamMappings,
      manageRoster,
      addTeamMapping,
      removeTeamMapping,
      closeModals,
      closeMappingsModal,
      closeRosterModal,
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
  background: rgb(var(--color-card));
  border-radius: 8px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
</style>
