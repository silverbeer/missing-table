<template>
  <div>
    <!-- Filters Section -->
    <div class="mb-6 space-y-4">
      <!-- Age Group Links -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ageGroup in ageGroups"
            :key="ageGroup.id"
            @click="selectedAgeGroupId = ageGroup.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedAgeGroupId === ageGroup.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
          >
            {{ ageGroup.name }}
          </button>
        </div>
      </div>

      <!-- Club Filter -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">Parent Club</h3>
        <div class="flex flex-wrap gap-2">
          <button
            @click="selectedClubId = null"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedClubId === null
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
          >
            All Clubs
          </button>
          <button
            v-for="club in clubs"
            :key="club.id"
            @click="selectedClubId = club.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedClubId === club.id
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
          >
            {{ club.name }}
          </button>
        </div>
      </div>

      <!-- League Selector -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">League</h3>
        <div v-if="authStore.isAdmin.value" class="flex flex-wrap gap-2">
          <button
            v-for="league in leagues"
            :key="league.id"
            @click="selectedLeagueId = league.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedLeagueId === league.id
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
          >
            {{ league.name }}
          </button>
        </div>
        <div v-else class="flex flex-wrap gap-2">
          <div
            class="px-4 py-2 text-sm rounded-md font-medium bg-gray-50 text-gray-700 border border-gray-300"
          >
            {{ selectedLeagueName || 'No league assigned' }}
          </div>
        </div>
      </div>

      <!-- Season and Division Row -->
      <div
        class="flex flex-col sm:flex-row sm:space-x-6 space-y-4 sm:space-y-0"
      >
        <!-- Season Dropdown -->
        <div class="flex-1">
          <h3 class="text-sm font-medium text-gray-700 mb-3">Season</h3>
          <select
            v-model="selectedSeasonId"
            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option
              v-for="season in seasons"
              :key="season.id"
              :value="season.id"
            >
              {{ season.name }} ({{ formatSeasonDates(season) }})
            </option>
          </select>
        </div>

        <!-- Division Dropdown -->
        <div class="flex-1">
          <h3 class="text-sm font-medium text-gray-700 mb-3">Division</h3>
          <select
            v-model="selectedDivisionId"
            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option
              v-for="division in divisions"
              :key="division.id"
              :value="division.id"
            >
              {{ division.leagues?.name || 'Unknown League' }} -
              {{ division.name }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div class="overflow-x-auto">
      <!-- Loading State -->
      <div v-if="loading" class="text-center py-4">Loading table data...</div>

      <!-- Error State -->
      <div v-else-if="error" class="text-center py-4 text-red-600">
        Error: {{ error }}
      </div>

      <!-- Table -->
      <table v-else class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Pos
            </th>
            <th
              class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Team
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GP
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              W
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              D
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              L
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GF
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GA
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GD
            </th>
            <th
              class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Pts
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="(team, index) in tableData" :key="team.team">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ index + 1 }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              {{ getTeamDisplayName(team.team) }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.played }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.wins }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.draws }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.losses }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goals_for }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goals_against }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goal_difference }}
            </td>
            <td
              class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.points }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue';
import { useAuthStore } from '../stores/auth';

export default {
  name: 'LeagueTable',
  setup() {
    const authStore = useAuthStore();
    const tableData = ref([]);
    const teams = ref([]); // Store all teams for name→id mapping
    const teamAliases = ref({}); // team_id → external_name mapping
    const ageGroups = ref([]);
    const clubs = ref([]);
    const leagues = ref([]);
    const divisions = ref([]);
    const allDivisions = ref([]); // Store all divisions for filtering
    const seasons = ref([]);
    const selectedAgeGroupId = ref(2); // Default to U14
    const selectedClubId = ref(null); // Default to all clubs
    const selectedLeagueId = ref(null); // Default to first league
    const selectedDivisionId = ref(1); // Default to Northeast
    const selectedSeasonId = ref(2); // Default to 2024-2025
    const error = ref(null);
    const loading = ref(true);

    // Computed property for selected league name
    const selectedLeagueName = computed(() => {
      const league = leagues.value.find(l => l.id === selectedLeagueId.value);
      return league ? league.name : '';
    });

    const fetchAgeGroups = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups`
        );
        ageGroups.value = data.sort((a, b) => a.name.localeCompare(b.name));

        // Set U14 as default if available
        const u14 = data.find(ag => ag.name === 'U14');
        if (u14) {
          selectedAgeGroupId.value = u14.id;
        }
      } catch (err) {
        console.error('Error fetching age groups:', err);
      }
    };

    const fetchClubs = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/clubs`
        );
        clubs.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching clubs:', err);
        // Not a fatal error - clubs filter is optional
      }
    };

    const fetchTeams = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`
        );
        teams.value = data;
      } catch (err) {
        console.error('Error fetching teams:', err);
      }
    };

    const fetchLeagues = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues`
        );
        leagues.value = data.sort((a, b) => a.name.localeCompare(b.name));

        // Set Homegrown as default if available
        const homegrown = data.find(l => l.name === 'Homegrown');
        if (homegrown) {
          selectedLeagueId.value = homegrown.id;
        } else if (data.length > 0) {
          selectedLeagueId.value = data[0].id;
        }
      } catch (err) {
        console.error('Error fetching leagues:', err);
      }
    };

    const fetchTeamAliases = async leagueId => {
      if (!leagueId) {
        teamAliases.value = {};
        return;
      }

      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues/${leagueId}/team-aliases`
        );
        teamAliases.value = data;
        console.log('Team aliases loaded for league:', leagueId, data);
      } catch (err) {
        console.error('Error fetching team aliases:', err);
        teamAliases.value = {}; // Clear on error
      }
    };

    const filterDivisionsByLeague = () => {
      if (selectedLeagueId.value) {
        divisions.value = allDivisions.value.filter(
          d => d.league_id === selectedLeagueId.value
        );
        // Reset division selection if current division is not in filtered list
        if (!divisions.value.find(d => d.id === selectedDivisionId.value)) {
          if (divisions.value.length > 0) {
            selectedDivisionId.value = divisions.value[0].id;
          }
        }
      } else {
        divisions.value = allDivisions.value;
      }
    };

    const fetchDivisions = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/divisions`
        );
        allDivisions.value = data.sort((a, b) => a.name.localeCompare(b.name));

        // Filter divisions by selected league
        filterDivisionsByLeague();

        // Set Northeast as default if available in filtered divisions
        const northeast = divisions.value.find(d => d.name === 'Northeast');
        if (northeast) {
          selectedDivisionId.value = northeast.id;
        } else if (divisions.value.length > 0) {
          selectedDivisionId.value = divisions.value[0].id;
        }
      } catch (err) {
        console.error('Error fetching divisions:', err);
      }
    };

    const fetchSeasons = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons`
        );
        // Sort seasons by start date (most recent first)
        seasons.value = data.sort(
          (a, b) => new Date(b.start_date) - new Date(a.start_date)
        );

        // Set 2025-2026 as default if available
        const currentSeason = data.find(s => s.name === '2025-2026');
        if (currentSeason) {
          selectedSeasonId.value = currentSeason.id;
        }
      } catch (err) {
        console.error('Error fetching seasons:', err);
      }
    };

    const formatSeasonDates = season => {
      const startYear = new Date(season.start_date).getFullYear();
      const endYear = new Date(season.end_date).getFullYear();
      return `${startYear}-${endYear}`;
    };

    // Get team display name with alias support
    const getTeamDisplayName = teamName => {
      // Find the team by name to get its ID
      const team = teams.value.find(t => t.name === teamName);
      if (!team) {
        return teamName; // Fallback to original name if team not found
      }

      // If we have an alias for this team in the selected league, use it
      if (selectedLeagueId.value && teamAliases.value[team.id]) {
        return teamAliases.value[team.id];
      }

      // Otherwise, fall back to the team's actual name
      return teamName;
    };

    const fetchTableData = async () => {
      loading.value = true;
      console.log('Fetching table data...', {
        seasonId: selectedSeasonId.value,
        ageGroupId: selectedAgeGroupId.value,
        divisionId: selectedDivisionId.value,
        clubId: selectedClubId.value,
      });
      try {
        let url = `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/table?season_id=${selectedSeasonId.value}&age_group_id=${selectedAgeGroupId.value}&division_id=${selectedDivisionId.value}`;

        // Add club_id parameter if a club is selected
        if (selectedClubId.value !== null) {
          url += `&club_id=${selectedClubId.value}`;
        }

        const data = await authStore.apiRequest(url);
        console.log('Table data received:', data);

        tableData.value = data;
        console.log('Table data set:', tableData.value);
      } catch (err) {
        console.error('Error fetching table data:', err);
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    // Watch for league changes to filter divisions and fetch team aliases
    watch(selectedLeagueId, newLeagueId => {
      filterDivisionsByLeague();
      if (newLeagueId) {
        fetchTeamAliases(newLeagueId);
      } else {
        teamAliases.value = {};
      }
    });

    // Watch for changes in filters and refetch data
    watch(
      [
        selectedSeasonId,
        selectedAgeGroupId,
        selectedDivisionId,
        selectedClubId,
      ],
      () => {
        fetchTableData();
      }
    );

    onMounted(async () => {
      console.log('LeagueTable component mounted');
      await Promise.all([
        fetchAgeGroups(),
        fetchClubs(),
        fetchLeagues(),
        fetchSeasons(),
        fetchTeams(),
      ]);
      // Fetch divisions after leagues are loaded so we can filter by default league
      await fetchDivisions();

      // Fetch team aliases for the initially selected league
      if (selectedLeagueId.value) {
        await fetchTeamAliases(selectedLeagueId.value);
      }

      // For non-admins, auto-select based on their team's league and division
      if (!authStore.isAdmin.value && authStore.userTeamId.value) {
        try {
          // Fetch the user's team to get its league and division
          const teams = await authStore.apiRequest(
            `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`
          );
          const userTeam = teams.find(t => t.id === authStore.userTeamId.value);

          if (userTeam) {
            // Get division for selected age group
            const division =
              userTeam.divisions_by_age_group[selectedAgeGroupId.value];
            if (division) {
              selectedLeagueId.value = division.league_id;
              selectedDivisionId.value = division.id;

              // Re-filter divisions by league
              filterDivisionsByLeague();
            }
          }
        } catch (err) {
          console.error('Error fetching user team info:', err);
        }
      }

      fetchTableData();
    });

    return {
      tableData,
      ageGroups,
      clubs,
      leagues,
      divisions,
      seasons,
      selectedAgeGroupId,
      selectedClubId,
      selectedLeagueId,
      selectedLeagueName,
      selectedDivisionId,
      selectedSeasonId,
      formatSeasonDates,
      getTeamDisplayName,
      error,
      loading,
      authStore,
    };
  },
};
</script>
