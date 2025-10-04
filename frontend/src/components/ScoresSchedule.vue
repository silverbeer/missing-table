<template>
  <div>
    <!-- Loading State -->
    <div v-if="loading" class="text-center py-4">
      Loading teams and games...
    </div>

    <!-- Error State -->
    <div v-if="error" class="text-red-600 p-4 mb-4">Error: {{ error }}</div>

    <div v-else>
      <!-- Filters Section -->
      <div class="mb-6 space-y-4">
        <!-- Age Group and Season Row -->
        <div
          class="flex flex-col sm:flex-row sm:space-x-6 space-y-4 sm:space-y-0"
        >
          <!-- Age Group Links -->
          <div class="flex-1">
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
        </div>

        <!-- Team Filter -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1"
            >Select Team</label
          >
          <select
            v-model="selectedTeam"
            @change="onTeamChange"
            class="mt-1 block w-full max-w-md rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">All Teams</option>
            <option
              v-for="team in filteredTeams"
              :key="team.id"
              :value="team.id"
            >
              {{ team.name }}
            </option>
          </select>
        </div>

        <!-- Game Type Filter -->
        <div>
          <h3 class="text-sm font-medium text-gray-700 mb-3">Game Type</h3>
          <div class="flex flex-wrap gap-2">
            <button
              @click="selectedGameTypeId = 1"
              :class="[
                'px-4 py-2 text-sm rounded-md font-medium transition-colors',
                selectedGameTypeId === 1
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              League
            </button>
            <button
              @click="selectedGameTypeId = 3"
              :class="[
                'px-4 py-2 text-sm rounded-md font-medium transition-colors',
                selectedGameTypeId === 3
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              Friendly
            </button>
            <button
              @click="selectedGameTypeId = 2"
              :class="[
                'px-4 py-2 text-sm rounded-md font-medium transition-colors',
                selectedGameTypeId === 2
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              Tournament
            </button>
            <button
              @click="selectedGameTypeId = 4"
              :class="[
                'px-4 py-2 text-sm rounded-md font-medium transition-colors',
                selectedGameTypeId === 4
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              Playoff
            </button>
            <button
              @click="selectedGameTypeId = null"
              :class="[
                'px-4 py-2 text-sm rounded-md font-medium transition-colors',
                selectedGameTypeId === null
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              All Games
            </button>
          </div>
        </div>
      </div>

      <!-- Display Filtered Games -->
      <div v-if="sortedGames.length > 0">
        <div class="mb-4">
          <h3 class="text-lg font-semibold mb-2">
            Games for {{ getSelectedTeamName() }}
          </h3>

          <!-- League Information -->
          <div
            v-if="selectedTeamLeagueInfo"
            class="inline-flex items-center space-x-2 px-3 py-1 bg-blue-50 border border-blue-200 rounded-md text-sm"
          >
            <span class="font-medium text-blue-800">League:</span>
            <span class="text-blue-700"
              >{{ selectedTeamLeagueInfo.ageGroup }}
              {{ selectedTeamLeagueInfo.division }}</span
            >
            <span class="text-blue-600">• {{ selectedSeasonName }}</span>
          </div>
        </div>

        <!-- Season Summary Stats -->
        <div class="mb-4 space-y-4">
          <div class="p-3 bg-gray-50 rounded-md border border-gray-200">
            <h4 class="font-medium text-gray-700 mb-2">Season Summary</h4>
            <div class="grid grid-cols-4 gap-2 text-sm">
              <div class="font-medium">GP: {{ seasonStats.gamesPlayed }}</div>
              <div class="font-medium">W: {{ seasonStats.wins }}</div>
              <div class="font-medium">D: {{ seasonStats.draws }}</div>
              <div class="font-medium">L: {{ seasonStats.losses }}</div>
              <div>GF: {{ seasonStats.goalsFor }}</div>
              <div>GA: {{ seasonStats.goalsAgainst }}</div>
              <div>
                GD: {{ seasonStats.goalDifference > 0 ? '+' : ''
                }}{{ seasonStats.goalDifference }}
              </div>
              <div class="font-bold">PTS: {{ seasonStats.points }}</div>
            </div>
          </div>

          <!-- Season Segments - Only show if games exist in those periods -->
          <div class="grid gap-4" :class="getSegmentGridClass()">
            <!-- Fall Segment - Only show if Fall games exist -->
            <div
              v-if="seasonStats.hasFallGames"
              class="p-3 bg-blue-50 rounded-md border border-blue-100"
            >
              <h4 class="font-medium text-blue-700 mb-2">Fall Segment</h4>
              <div class="grid grid-cols-3 gap-2 text-sm">
                <div class="font-medium">
                  W: {{ seasonStats.fallWins || 0 }}
                </div>
                <div class="font-medium">
                  D: {{ seasonStats.fallDraws || 0 }}
                </div>
                <div class="font-medium">
                  L: {{ seasonStats.fallLosses || 0 }}
                </div>
                <div class="col-span-3 text-xs text-gray-500">
                  Aug - Dec games
                </div>
              </div>
            </div>

            <!-- Spring Segment - Only show if Spring games exist -->
            <div
              v-if="seasonStats.hasSpringGames"
              class="p-3 bg-green-50 rounded-md border border-green-100"
            >
              <h4 class="font-medium text-green-700 mb-2">Spring Segment</h4>
              <div class="grid grid-cols-3 gap-2 text-sm">
                <div class="font-medium">
                  W: {{ seasonStats.springWins || 0 }}
                </div>
                <div class="font-medium">
                  D: {{ seasonStats.springDraws || 0 }}
                </div>
                <div class="font-medium">
                  L: {{ seasonStats.springLosses || 0 }}
                </div>
                <div class="col-span-3 text-xs text-gray-500">
                  Jan - July games
                </div>
              </div>
            </div>

            <!-- Last 5 Games - Only show if games exist -->
            <div
              v-if="seasonStats.gamesPlayed > 0"
              class="p-3 bg-purple-50 rounded-md border border-purple-100"
            >
              <h4 class="font-medium text-purple-700 mb-2">Last 5 Games</h4>
              <div class="flex space-x-1">
                <template v-if="seasonStats.lastFive.length > 0">
                  <span
                    v-for="(result, index) in seasonStats.lastFive"
                    :key="index"
                    class="w-6 h-6 flex items-center justify-center rounded-full text-xs font-medium"
                    :class="{
                      'bg-green-100 text-green-800': result === 'W',
                      'bg-yellow-100 text-yellow-800': result === 'D',
                      'bg-red-100 text-red-800': result === 'L',
                      'bg-gray-100 text-gray-500': result === '-',
                    }"
                  >
                    {{ result }}
                  </span>
                </template>
                <span v-else class="text-sm text-gray-500"
                  >No recent games</span
                >
              </div>
            </div>
          </div>
        </div>
        <table class="w-full border border-gray-300 table-fixed">
          <thead>
            <tr>
              <th class="border-b text-right w-12">#</th>
              <th class="border-b text-center w-32">Date</th>
              <th class="border-b text-left px-2">Team</th>
              <th class="border-b text-center w-24">Score</th>
              <th class="border-b text-center w-24">Game Type</th>
              <th class="border-b text-center w-24">Status</th>
              <th class="border-b text-right w-20">Result</th>
              <th v-if="canEditGames" class="border-b text-center w-24">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(game, index) in sortedGames"
              :key="game.game_date"
              :class="{ 'bg-gray-100': index % 2 === 0 }"
            >
              <td class="border-b text-right">{{ index + 1 }}</td>
              <td class="border-b text-center">{{ game.game_date }}</td>
              <td class="border-b text-left px-2">
                {{ getTeamDisplay(game) }}
              </td>
              <td class="border-b text-center">
                {{ game.home_score }} - {{ game.away_score }}
              </td>
              <td class="border-b text-center">
                {{ game.game_type_name || 'League' }}
              </td>
              <td class="border-b text-center">
                <span
                  :class="{
                    'px-2 py-1 rounded text-xs font-medium': true,
                    'bg-green-100 text-green-800':
                      game.match_status === 'played',
                    'bg-blue-100 text-blue-800':
                      game.match_status === 'scheduled',
                    'bg-yellow-100 text-yellow-800':
                      game.match_status === 'postponed',
                    'bg-red-100 text-red-800':
                      game.match_status === 'cancelled',
                    'bg-gray-100 text-gray-800': !game.match_status,
                  }"
                >
                  {{ game.match_status || 'scheduled' }}
                </span>
              </td>
              <td class="border-b text-right">{{ getResult(game) }}</td>
              <td v-if="canEditGames" class="border-b text-center">
                <button
                  v-if="canEditGame(game)"
                  @click="editGame(game)"
                  class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  Edit
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else>
        <p>No games found for the selected team.</p>
      </div>
    </div>

    <!-- Game Edit Modal -->
    <GameEditModal
      :show="showEditModal"
      :game="editingGame"
      :teams="teams"
      :seasons="seasons"
      :game-types="gameTypes"
      :age-groups="ageGroups"
      @close="closeEditModal"
      @updated="onGameUpdated"
    />
  </div>
</template>

<script>
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import GameEditModal from '@/components/GameEditModal.vue';

export default {
  name: 'ScoresSchedule',
  components: {
    GameEditModal,
  },
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const games = ref([]);
    const ageGroups = ref([]);
    const seasons = ref([]);
    const gameTypes = ref([]);
    const selectedTeam = ref('');
    const selectedAgeGroupId = ref(2); // Default to U14
    const selectedSeasonId = ref(3); // Default to 2025-2026
    const selectedGameTypeId = ref(1); // Default to League games (id: 1)
    const error = ref(null);
    const loading = ref(true);
    const showEditModal = ref(false);
    const editingGame = ref(null);

    const fetchAgeGroups = async () => {
      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups`
        );
        if (!response.ok) throw new Error('Failed to fetch age groups');
        const data = await response.json();
        ageGroups.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching age groups:', err);
      }
    };

    const fetchSeasons = async () => {
      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons`
        );
        if (!response.ok) throw new Error('Failed to fetch seasons');
        const data = await response.json();
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

    const fetchGameTypes = async () => {
      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/game-types`
        );
        if (!response.ok) throw new Error('Failed to fetch game types');
        gameTypes.value = await response.json();
      } catch (err) {
        console.error('Error fetching game types:', err);
      }
    };

    const fetchTeams = async () => {
      try {
        const response = await fetch(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`
        );
        if (!response.ok) {
          throw new Error('Failed to fetch teams');
        }
        teams.value = await response.json();

        // Auto-select player's team if they're logged in
        if (authStore.userTeamId && !selectedTeam.value) {
          const playerTeam = teams.value.find(
            team => team.id === authStore.userTeamId
          );
          if (playerTeam) {
            selectedTeam.value = String(authStore.userTeamId);
            // Fetch games for the player's team
            await fetchGames();
          }
        }
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchGames = async () => {
      // Guard against unauthorized access
      if (!authStore.isAuthenticated.value) {
        console.warn('User not authenticated, cannot fetch games');
        return;
      }

      if (!selectedTeam.value) {
        console.log('No team selected, skipping fetch.');
        games.value = []; // Clear games if no team is selected
        return; // Exit the function early
      }

      try {
        console.log(
          'Fetching games for team:',
          selectedTeam.value,
          'season:',
          selectedSeasonId.value
        );
        const url = `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/games/team/${selectedTeam.value}?season_id=${selectedSeasonId.value}`;
        games.value = await authStore.apiRequest(url);
        console.log('Games received:', games.value);
      } catch (err) {
        error.value = err.message;
      }
    };

    const onTeamChange = async () => {
      console.log('Selected team:', selectedTeam.value);
      await fetchGames();
    };

    const getTeamDisplay = game => {
      const selectedTeamId = parseInt(selectedTeam.value);
      if (game.home_team_id === selectedTeamId) {
        return `vs ${game.away_team_name}`;
      } else {
        return `@ ${game.home_team_name}`;
      }
    };

    const getSelectedTeamName = () => {
      const team = teams.value.find(t => t.id === parseInt(selectedTeam.value));
      return team ? team.name : 'Selected Team';
    };

    const getResult = game => {
      const gameDate = new Date(game.game_date);
      const currentDate = new Date();

      // Check if the game date is in the future
      if (gameDate > currentDate) {
        return 'Scheduled'; // Return 'Scheduled' for future games
      }

      // Determine the result for past games
      const selectedTeamId = parseInt(selectedTeam.value);
      if (game.home_team_id === selectedTeamId) {
        return game.home_score > game.away_score
          ? 'W'
          : game.home_score < game.away_score
            ? 'L'
            : 'T';
      } else if (game.away_team_id === selectedTeamId) {
        return game.away_score > game.home_score
          ? 'W'
          : game.away_score < game.home_score
            ? 'L'
            : 'T';
      }
      return ''; // Return empty if the selected team is not involved in the game
    };

    const formatSeasonDates = season => {
      const startYear = new Date(season.start_date).getFullYear();
      const endYear = new Date(season.end_date).getFullYear();
      return `${startYear}-${endYear}`;
    };

    const getSegmentGridClass = () => {
      const segmentCount =
        (seasonStats.value.hasFallGames ? 1 : 0) +
        (seasonStats.value.hasSpringGames ? 1 : 0) +
        (seasonStats.value.gamesPlayed > 0 ? 1 : 0);

      if (segmentCount <= 1) return 'grid-cols-1';
      if (segmentCount === 2) return 'grid-cols-1 md:grid-cols-2';
      return 'grid-cols-1 md:grid-cols-3';
    };

    // Filter teams based on selected age group
    const filteredTeams = computed(() => {
      return teams.value.filter(team => {
        return team.age_groups.some(ag => ag.id === selectedAgeGroupId.value);
      });
    });

    // Get league information for selected team
    const selectedTeamLeagueInfo = computed(() => {
      if (!selectedTeam.value) return null;

      const team = teams.value.find(t => t.id === parseInt(selectedTeam.value));
      if (!team) return null;

      const ageGroup = team.age_groups.find(
        ag => ag.id === selectedAgeGroupId.value
      );
      const division = team.divisions_by_age_group[selectedAgeGroupId.value];

      if (ageGroup && division) {
        return {
          ageGroup: ageGroup.name,
          division: division.name,
        };
      }

      return null;
    });

    // Get selected season name
    const selectedSeasonName = computed(() => {
      const season = seasons.value.find(s => s.id === selectedSeasonId.value);
      return season ? season.name : '';
    });

    // Sort games by date in ascending order for display and filter by game type
    const sortedGames = computed(() => {
      let filteredGames = [...games.value];

      // Filter by game type if a specific type is selected (not "All Games")
      if (selectedGameTypeId.value !== null) {
        filteredGames = filteredGames.filter(
          game => game.game_type_id === selectedGameTypeId.value
        );
      }

      return filteredGames.sort(
        (a, b) => new Date(a.game_date) - new Date(b.game_date)
      );
    });

    // Calculate season statistics based on selected game type filter
    const seasonStats = computed(() => {
      const currentDate = new Date();
      const stats = {
        gamesPlayed: 0,
        wins: 0,
        draws: 0,
        losses: 0,
        goalsFor: 0,
        goalsAgainst: 0,
        goalDifference: 0,
        points: 0,
        fallWins: 0,
        fallDraws: 0,
        fallLosses: 0,
        springWins: 0,
        springDraws: 0,
        springLosses: 0,
        hasFallGames: false,
        hasSpringGames: false,
        lastFive: [],
      };

      // Sort games by date (ascending order) and filter by selected game type
      let sortedGames = [...games.value].filter(
        game => new Date(game.game_date) <= currentDate
      );

      // Apply game type filter if a specific type is selected
      if (selectedGameTypeId.value !== null) {
        sortedGames = sortedGames.filter(
          game => game.game_type_id === selectedGameTypeId.value
        );
      }

      sortedGames = sortedGames.sort(
        (a, b) => new Date(a.game_date) - new Date(b.game_date)
      );

      sortedGames.forEach(game => {
        const selectedTeamId = parseInt(selectedTeam.value);
        const isHome = game.home_team_id === selectedTeamId;
        const isAway = game.away_team_id === selectedTeamId;

        if (isHome || isAway) {
          const teamScore = isHome ? game.home_score : game.away_score;
          const opponentScore = isHome ? game.away_score : game.home_score;

          // Basic stats
          stats.gamesPlayed++;
          stats.goalsFor += teamScore;
          stats.goalsAgainst += opponentScore;

          // Determine result
          let result = '';
          if (teamScore > opponentScore) {
            result = 'W';
            stats.wins++;
          } else if (teamScore < opponentScore) {
            result = 'L';
            stats.losses++;
          } else {
            result = 'D';
            stats.draws++;
          }

          // Determine if game is in Fall or Spring segment based on month
          const gameDate = new Date(game.game_date);
          const month = String(gameDate.getMonth() + 1).padStart(2, '0');
          const isFall = ['08', '09', '10', '11', '12'].includes(month);

          // Track that games exist in these periods
          if (isFall) {
            stats.hasFallGames = true;
            if (result === 'W') stats.fallWins++;
            else if (result === 'D') stats.fallDraws++;
            else stats.fallLosses++;
          } else {
            stats.hasSpringGames = true;
            if (result === 'W') stats.springWins++;
            else if (result === 'D') stats.springDraws++;
            else stats.springLosses++;
          }

          // Track last 5 games (will be reversed later to show most recent first)
          if (stats.lastFive.length < 5) {
            stats.lastFive.push(result);
          }
        }
      });

      // Reverse lastFive to show most recent games first
      stats.lastFive = stats.lastFive.reverse();

      // Calculate final stats
      stats.goalDifference = stats.goalsFor - stats.goalsAgainst;
      stats.points = stats.wins * 3 + stats.draws * 1;

      return stats;
    });

    // Watch for changes in age group and season to refresh teams and clear selection
    watch([selectedAgeGroupId, selectedSeasonId], () => {
      // Only clear selection if it's not the player's team
      if (authStore.userTeamId) {
        const playerTeamStillAvailable = filteredTeams.value.some(
          team => team.id === authStore.userTeamId
        );
        if (!playerTeamStillAvailable) {
          selectedTeam.value = ''; // Clear if player's team not in filtered list
        }
      } else {
        selectedTeam.value = ''; // Clear team selection when filters change
      }
      games.value = []; // Clear games
    });

    // Watch for team changes to fetch games
    watch(selectedTeam, () => {
      fetchGames();
    });

    // Watch for season changes to refetch games if team is selected
    watch(selectedSeasonId, () => {
      if (selectedTeam.value) {
        fetchGames();
      }
    });

    // Watch for auth changes to auto-select player's team
    watch(
      () => authStore.userTeamId,
      newTeamId => {
        if (newTeamId && teams.value.length > 0) {
          const playerTeam = filteredTeams.value.find(
            team => team.id === newTeamId
          );
          if (playerTeam) {
            selectedTeam.value = String(newTeamId);
          }
        }
      }
    );

    // Permission checks
    const canEditGames = computed(() => {
      return authStore.isAdmin || authStore.isTeamManager;
    });

    const canEditGame = game => {
      // Admins can edit all games
      if (authStore.isAdmin) {
        return true;
      }

      // Team managers can only edit games involving their team
      if (authStore.isTeamManager && authStore.userTeamId) {
        return (
          game.home_team_id === authStore.userTeamId ||
          game.away_team_id === authStore.userTeamId
        );
      }

      return false;
    };

    const editGame = game => {
      editingGame.value = game;
      showEditModal.value = true;
    };

    const closeEditModal = () => {
      showEditModal.value = false;
      editingGame.value = null;
    };

    const onGameUpdated = () => {
      // Refresh the games list after a successful update
      fetchGames();
    };

    onMounted(async () => {
      // Only fetch data if user is authenticated
      if (!authStore.isAuthenticated.value) {
        console.warn('User not authenticated, skipping data fetch');
        loading.value = false;
        error.value = 'Please log in to view games';
        return;
      }

      await Promise.all([
        fetchAgeGroups(),
        fetchSeasons(),
        fetchGameTypes(),
        fetchTeams(),
      ]);
    });

    return {
      teams,
      games,
      sortedGames,
      ageGroups,
      seasons,
      gameTypes,
      selectedTeam,
      selectedAgeGroupId,
      selectedSeasonId,
      selectedGameTypeId,
      filteredTeams,
      selectedTeamLeagueInfo,
      selectedSeasonName,
      error,
      loading,
      onTeamChange,
      getResult,
      seasonStats,
      getTeamDisplay,
      getSelectedTeamName,
      formatSeasonDates,
      getSegmentGridClass,
      canEditGames,
      canEditGame,
      editGame,
      closeEditModal,
      onGameUpdated,
      showEditModal,
      editingGame,
    };
  },
};
</script>
