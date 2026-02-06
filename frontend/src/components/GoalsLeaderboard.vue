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

      <!-- Match Type Filter -->
      <div data-testid="match-type-filter">
        <h3 class="text-sm font-medium text-gray-700 mb-3">Match Type</h3>
        <div class="flex flex-wrap gap-2">
          <button
            @click="selectedMatchTypeId = null"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedMatchTypeId === null
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
            data-testid="match-type-all"
          >
            All
          </button>
          <button
            v-for="mt in matchTypes"
            :key="mt.id"
            @click="selectedMatchTypeId = mt.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedMatchTypeId === mt.id
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
            :data-testid="`match-type-${mt.name}`"
          >
            {{ mt.name }}
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
            <option :value="null">All Divisions</option>
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
        Loading leaderboard...
      </div>

      <!-- Error State -->
      <div
        v-else-if="error"
        class="text-center py-4 text-red-600"
        data-testid="error-message"
      >
        Error: {{ error }}
      </div>

      <!-- Empty State -->
      <div
        v-else-if="leaderboardData.length === 0"
        class="text-center py-8 text-gray-500"
      >
        No goal scorers found for the selected filters.
      </div>

      <!-- Leaderboard Table -->
      <table
        v-else
        class="min-w-full divide-y divide-gray-200"
        data-testid="leaderboard-table"
      >
        <thead class="bg-gray-50">
          <tr>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Rank
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Player
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-[100px] sm:max-w-[140px] md:max-w-none"
            >
              Team
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Goals
            </th>
            <th
              class="hidden sm:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Games
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Goals/Game
            </th>
          </tr>
        </thead>
        <tbody
          class="bg-white divide-y divide-gray-200"
          data-testid="leaderboard-body"
        >
          <tr
            v-for="player in leaderboardData"
            :key="player.player_id"
            data-testid="leaderboard-row"
            class="hover:bg-gray-50"
          >
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-gray-500"
            >
              <span
                :class="[
                  'inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium',
                  player.rank === 1
                    ? 'bg-yellow-100 text-yellow-800'
                    : player.rank === 2
                      ? 'bg-gray-200 text-gray-700'
                      : player.rank === 3
                        ? 'bg-orange-100 text-orange-800'
                        : 'bg-transparent text-gray-500',
                ]"
              >
                {{ player.rank }}
              </span>
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm font-medium text-gray-900"
            >
              <div class="flex items-center">
                <span
                  v-if="player.jersey_number"
                  class="text-gray-400 text-xs mr-2"
                  >#{{ player.jersey_number }}</span
                >
                <span>{{ formatPlayerName(player) }}</span>
              </div>
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 text-xs sm:text-sm text-gray-500 max-w-[100px] sm:max-w-[140px] md:max-w-none truncate"
            >
              {{ player.team_name || 'Unknown' }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center font-semibold text-gray-900"
            >
              {{ player.goals }}
            </td>
            <td
              class="hidden sm:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ player.games_played }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-gray-500"
            >
              {{ player.goals_per_game }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

export default {
  name: 'GoalsLeaderboard',
  setup() {
    const authStore = useAuthStore();
    const leaderboardData = ref([]);
    const ageGroups = ref([]);
    const leagues = ref([]);
    const divisions = ref([]);
    const allDivisions = ref([]);
    const seasons = ref([]);
    const matchTypes = ref([]);
    const selectedAgeGroupId = ref(null);
    const selectedLeagueId = ref(null);
    const selectedDivisionId = ref(null);
    const selectedSeasonId = ref(null);
    const selectedMatchTypeId = ref(null);
    const error = ref(null);
    const loading = ref(true);

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
        } else if (data.length > 0) {
          selectedAgeGroupId.value = data[0].id;
        }
      } catch (err) {
        console.error('Error fetching age groups:', err);
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

    const fetchMatchTypes = async () => {
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/match-types`
        );
        matchTypes.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching match types:', err);
      }
    };

    const filterDivisionsByLeague = () => {
      if (selectedLeagueId.value) {
        divisions.value = allDivisions.value.filter(
          d => Number(d.league_id) === Number(selectedLeagueId.value)
        );
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
        filterDivisionsByLeague();
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
        } else if (data.length > 0) {
          selectedSeasonId.value = data[0].id;
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

    const formatPlayerName = player => {
      if (player.first_name && player.last_name) {
        return `${player.first_name} ${player.last_name}`;
      }
      return player.first_name || player.last_name || 'Unknown Player';
    };

    const fetchLeaderboardData = async () => {
      if (!selectedSeasonId.value) {
        return;
      }

      loading.value = true;
      error.value = null;

      try {
        let url = `${getApiBaseUrl()}/api/leaderboards/goals?season_id=${selectedSeasonId.value}`;

        if (selectedLeagueId.value) {
          url += `&league_id=${selectedLeagueId.value}`;
        }
        if (selectedDivisionId.value) {
          url += `&division_id=${selectedDivisionId.value}`;
        }
        if (selectedAgeGroupId.value) {
          url += `&age_group_id=${selectedAgeGroupId.value}`;
        }
        if (selectedMatchTypeId.value) {
          url += `&match_type_id=${selectedMatchTypeId.value}`;
        }

        console.log('Fetching leaderboard:', url);
        const data = await authStore.apiRequest(url);
        console.log('Leaderboard data received:', data);

        if (!Array.isArray(data)) {
          console.error('Unexpected data format:', data);
          error.value = 'Unexpected response format from server';
          leaderboardData.value = [];
          return;
        }

        leaderboardData.value = data;
      } catch (err) {
        console.error('Error fetching leaderboard data:', err);
        // Provide more helpful error messages
        if (err.message === 'Not Found') {
          error.value =
            'Leaderboard endpoint not available. Please try refreshing the page.';
        } else if (err.message.includes('Session expired')) {
          error.value = 'Your session has expired. Please log in again.';
        } else {
          error.value = err.message || 'Failed to load leaderboard data';
        }
      } finally {
        loading.value = false;
      }
    };

    // Watch for league changes to filter divisions
    watch(selectedLeagueId, () => {
      filterDivisionsByLeague();
      // Reset division selection when league changes
      selectedDivisionId.value = null;
    });

    // Watch for changes in filters and refetch data
    watch(
      [
        selectedSeasonId,
        selectedAgeGroupId,
        selectedLeagueId,
        selectedDivisionId,
        selectedMatchTypeId,
      ],
      () => {
        if (selectedSeasonId.value) {
          fetchLeaderboardData();
        }
      }
    );

    onMounted(async () => {
      await Promise.all([
        fetchAgeGroups(),
        fetchLeagues(),
        fetchSeasons(),
        fetchMatchTypes(),
      ]);
      await fetchDivisions();
      fetchLeaderboardData();
    });

    return {
      leaderboardData,
      ageGroups,
      leagues,
      divisions,
      seasons,
      matchTypes,
      selectedAgeGroupId,
      selectedLeagueId,
      selectedDivisionId,
      selectedSeasonId,
      selectedMatchTypeId,
      formatSeasonDates,
      formatPlayerName,
      error,
      loading,
    };
  },
};
</script>
