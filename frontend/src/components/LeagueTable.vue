<template>
  <div>
    <!-- Filters Section -->
    <div class="mb-6 space-y-4">
      <!-- Age Group Links -->
      <div data-testid="age-group-filter">
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
            :data-testid="`age-group-${ageGroup.name}`"
          >
            {{ ageGroup.name }}
          </button>
        </div>
      </div>

      <!-- League Selector -->
      <div>
        <h3 class="text-sm font-medium text-gray-700 mb-3">League</h3>
        <div class="flex flex-wrap gap-2">
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
            data-testid="season-filter"
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
            data-testid="division-filter"
          >
            <option
              v-for="division in divisions"
              :key="division.id"
              :value="division.id"
            >
              {{ division.name }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div class="overflow-x-auto">
      <!-- Loading State -->
      <div
        v-if="loading"
        class="text-center py-4"
        data-testid="loading-indicator"
      >
        Loading table data...
      </div>

      <!-- Error State -->
      <div
        v-else-if="error"
        class="text-center py-4 text-red-600"
        data-testid="error-message"
      >
        Error: {{ error }}
      </div>

      <!-- Table -->
      <table
        v-else
        class="min-w-full divide-y divide-gray-200"
        data-testid="standings-table"
      >
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-1 sm:px-2 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              #
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-[100px] sm:max-w-[140px] md:max-w-none"
            >
              Team
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GP
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              W
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              D
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              L
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GF
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GA
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              GD
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Pts
            </th>
          </tr>
        </thead>
        <tbody
          class="bg-white divide-y divide-gray-200"
          data-testid="standings-body"
        >
          <tr
            v-for="(team, index) in tableData"
            :key="team.team"
            data-testid="standings-row"
          >
            <td
              class="px-1 sm:px-2 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-gray-500"
            >
              {{ index + 1 }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 text-xs sm:text-sm font-medium text-gray-900 max-w-[100px] sm:max-w-[140px] md:max-w-none md:whitespace-nowrap"
            >
              {{ getTeamDisplayName(team.team) }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.played }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.wins }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.draws }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.losses }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goals_for }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goals_against }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ team.goal_difference }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center font-medium text-gray-900"
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
import { getApiBaseUrl } from '../config/api';

export default {
  name: 'LeagueTable',
  props: {
    initialAgeGroupId: {
      type: Number,
      default: null,
    },
    initialLeagueId: {
      type: Number,
      default: null,
    },
    initialDivisionId: {
      type: Number,
      default: null,
    },
    filterKey: {
      type: Number,
      default: 0,
    },
  },
  setup(props) {
    const authStore = useAuthStore();
    const tableData = ref([]);
    const teams = ref([]); // Store all teams for name→id mapping
    const ageGroups = ref([]);
    const leagues = ref([]);
    const divisions = ref([]);
    const allDivisions = ref([]); // Store all divisions for filtering
    const seasons = ref([]);
    const selectedAgeGroupId = ref(2); // Default to U14
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
          `${getApiBaseUrl()}/api/age-groups`
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

    const fetchTeams = async () => {
      try {
        const data = await authStore.apiRequest(`${getApiBaseUrl()}/api/teams`);
        teams.value = data;
      } catch (err) {
        console.error('Error fetching teams:', err);
      }
    };

    const fetchLeagues = async () => {
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues`
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

    // Filter leagues to only those where the user's club has teams
    const filterLeaguesByClub = () => {
      const clubId = authStore.userClubId.value;
      if (authStore.isAdmin.value || !clubId) return;

      const clubLeagueIds = new Set(
        teams.value
          .filter(t => t.club_id === clubId && t.league_id)
          .map(t => t.league_id)
      );

      if (clubLeagueIds.size > 0) {
        leagues.value = leagues.value.filter(l => clubLeagueIds.has(l.id));
        // Re-select default if current selection was filtered out
        if (!leagues.value.find(l => l.id === selectedLeagueId.value)) {
          const homegrown = leagues.value.find(l => l.name === 'Homegrown');
          selectedLeagueId.value = homegrown
            ? homegrown.id
            : leagues.value[0]?.id || null;
        }
      }
    };

    const filterDivisionsByLeague = () => {
      console.log('Filtering divisions by league:', {
        selectedLeagueId: selectedLeagueId.value,
        allDivisionsCount: allDivisions.value.length,
      });

      if (selectedLeagueId.value) {
        divisions.value = allDivisions.value.filter(
          d => Number(d.league_id) === Number(selectedLeagueId.value)
        );

        console.log('Filtered divisions:', {
          filteredCount: divisions.value.length,
          divisions: divisions.value.map(d => ({
            id: d.id,
            name: d.name,
            league_id: d.league_id,
          })),
        });

        // Reset division selection if current division is not in filtered list
        if (!divisions.value.find(d => d.id === selectedDivisionId.value)) {
          if (divisions.value.length > 0) {
            selectedDivisionId.value = divisions.value[0].id;
            console.log('Auto-selected division:', selectedDivisionId.value);
          }
        }
      } else {
        divisions.value = allDivisions.value;
      }
    };

    const fetchDivisions = async () => {
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/divisions`
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
          `${getApiBaseUrl()}/api/seasons`
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

    // Get team display name - now just returns the team name directly
    // Teams are scoped by league in the new clubs architecture
    const getTeamDisplayName = teamName => {
      return teamName;
    };

    const fetchTableData = async () => {
      loading.value = true;
      console.log('Fetching table data...', {
        seasonId: selectedSeasonId.value,
        ageGroupId: selectedAgeGroupId.value,
        divisionId: selectedDivisionId.value,
      });
      try {
        const url = `${getApiBaseUrl()}/api/table?season_id=${selectedSeasonId.value}&age_group_id=${selectedAgeGroupId.value}&division_id=${selectedDivisionId.value}`;

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
    watch(selectedLeagueId, () => {
      filterDivisionsByLeague();
    });

    // Watch for changes in filters and refetch data
    watch([selectedSeasonId, selectedAgeGroupId, selectedDivisionId], () => {
      fetchTableData();
    });

    // Watch for filterKey changes to apply external filters (from team card clicks)
    watch(
      () => props.filterKey,
      async newKey => {
        if (newKey > 0 && props.initialLeagueId) {
          console.log('Applying external filters:', {
            ageGroupId: props.initialAgeGroupId,
            leagueId: props.initialLeagueId,
            divisionId: props.initialDivisionId,
          });

          // Apply age group filter
          if (props.initialAgeGroupId) {
            selectedAgeGroupId.value = props.initialAgeGroupId;
          }

          // Apply league filter and re-filter divisions
          if (props.initialLeagueId) {
            selectedLeagueId.value = props.initialLeagueId;
            filterDivisionsByLeague();
          }

          // Apply division filter
          if (props.initialDivisionId) {
            selectedDivisionId.value = props.initialDivisionId;
          }

          // Fetch updated table data
          await fetchTableData();
        }
      }
    );

    onMounted(async () => {
      console.log('LeagueTable component mounted');
      console.log('Initial props:', {
        initialAgeGroupId: props.initialAgeGroupId,
        initialLeagueId: props.initialLeagueId,
        initialDivisionId: props.initialDivisionId,
        filterKey: props.filterKey,
      });

      await Promise.all([
        fetchAgeGroups(),
        fetchLeagues(),
        fetchSeasons(),
        fetchTeams(),
      ]);

      // Filter leagues to user's club before selecting defaults
      filterLeaguesByClub();

      // Fetch divisions after leagues are loaded so we can filter by default league
      await fetchDivisions();

      // Apply initial filters from props if provided (e.g., from team card click)
      if (props.filterKey > 0 && props.initialLeagueId) {
        console.log('Applying initial filters from props');
        if (props.initialAgeGroupId) {
          selectedAgeGroupId.value = props.initialAgeGroupId;
        }
        if (props.initialLeagueId) {
          selectedLeagueId.value = props.initialLeagueId;
          filterDivisionsByLeague();
        }
        if (props.initialDivisionId) {
          selectedDivisionId.value = props.initialDivisionId;
        }
      } else if (!authStore.isAdmin.value && authStore.userTeamId.value) {
        // For non-admins without explicit filters, auto-select based on their team
        try {
          // Fetch the user's team to get its league and division
          const teams = await authStore.apiRequest(
            `${getApiBaseUrl()}/api/teams`
          );
          const userTeam = teams.find(t => t.id === authStore.userTeamId.value);

          if (userTeam) {
            // Get division for selected age group
            // Ensure type-safe lookup: divisions_by_age_group uses string keys
            const division =
              userTeam.divisions_by_age_group[String(selectedAgeGroupId.value)];
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
      leagues,
      divisions,
      seasons,
      selectedAgeGroupId,
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
