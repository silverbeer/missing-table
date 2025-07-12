<template>
  <div>
    <!-- Loading State -->
    <div v-if="loading" class="text-center py-4">
      Loading teams and games...
    </div>

    <!-- Error State -->
    <div v-if="error" class="text-red-600 p-4 mb-4">
      Error: {{ error }}
    </div>

    <div v-else>
      <!-- Team Filter -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-1">Select Team</label>
        <select 
          v-model="selectedTeam"
          @change="onTeamChange"
          class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
        >
          <option value="">All Teams</option>
          <option v-for="team in teams" :key="team.id" :value="team.id">{{ team.name }}</option>
        </select>
      </div>

      <!-- Display Filtered Games -->
      <div v-if="games.length > 0">
        <h3 class="text-lg font-semibold mb-2">Games for {{ getSelectedTeamName() }}</h3>
        
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
              <div>GD: {{ seasonStats.goalDifference > 0 ? '+' : '' }}{{ seasonStats.goalDifference }}</div>
              <div class="font-bold">PTS: {{ seasonStats.points }}</div>
            </div>
          </div>

          <!-- Season Segments -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- Fall Segment -->
            <div class="p-3 bg-blue-50 rounded-md border border-blue-100">
              <h4 class="font-medium text-blue-700 mb-2">Fall Segment</h4>
              <div class="grid grid-cols-3 gap-2 text-sm">
                <div class="font-medium">W: {{ seasonStats.fallWins || 0 }}</div>
                <div class="font-medium">D: {{ seasonStats.fallDraws || 0 }}</div>
                <div class="font-medium">L: {{ seasonStats.fallLosses || 0 }}</div>
                <div class="col-span-3 text-xs text-gray-500">First half of season</div>
              </div>
            </div>

            <!-- Spring Segment -->
            <div class="p-3 bg-green-50 rounded-md border border-green-100">
              <h4 class="font-medium text-green-700 mb-2">Spring Segment</h4>
              <div class="grid grid-cols-3 gap-2 text-sm">
                <div class="font-medium">W: {{ seasonStats.springWins || 0 }}</div>
                <div class="font-medium">D: {{ seasonStats.springDraws || 0 }}</div>
                <div class="font-medium">L: {{ seasonStats.springLosses || 0 }}</div>
                <div class="col-span-3 text-xs text-gray-500">Second half of season</div>
              </div>
            </div>

            <!-- Last 5 Games -->
            <div class="p-3 bg-purple-50 rounded-md border border-purple-100">
              <h4 class="font-medium text-purple-700 mb-2">Last 5 Games</h4>
              <div class="flex space-x-1">
                <template v-if="seasonStats.lastFive.length > 0">
                  <span v-for="(result, index) in seasonStats.lastFive" :key="index" 
                        class="w-6 h-6 flex items-center justify-center rounded-full text-xs font-medium"
                        :class="{
                          'bg-green-100 text-green-800': result === 'W',
                          'bg-yellow-100 text-yellow-800': result === 'D',
                          'bg-red-100 text-red-800': result === 'L',
                          'bg-gray-100 text-gray-500': result === '-' 
                        }">
                    {{ result }}
                  </span>
                </template>
                <span v-else class="text-sm text-gray-500">No recent games</span>
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
              <th class="border-b text-right w-20">Result</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(game, index) in games" :key="game.game_date" :class="{'bg-gray-100': index % 2 === 0}">
              <td class="border-b text-right">{{ index + 1 }}</td>
              <td class="border-b text-center">{{ game.game_date }}</td>
              <td class="border-b text-left px-2">{{ getTeamDisplay(game) }}</td>
              <td class="border-b text-center">{{ game.home_score }} - {{ game.away_score }}</td>
              <td class="border-b text-right">{{ getResult(game) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else>
        <p>No games found for the selected team.</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue';

export default {
  name: 'ScoresSchedule',
  setup() {
    const teams = ref([]);
    const games = ref([]);
    const selectedTeam = ref('');
    const error = ref(null);
    const loading = ref(true);

    const fetchTeams = async () => {
      try {
        const response = await fetch(`${process.env.VUE_APP_API_URL}/teams`);
        if (!response.ok) {
          throw new Error('Failed to fetch teams');
        }
        teams.value = await response.json();
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchGames = async () => {
      if (!selectedTeam.value) {
        console.log('No team selected, skipping fetch.');
        games.value = []; // Clear games if no team is selected
        return; // Exit the function early
      }

      try {
        console.log('Fetching games for team:', selectedTeam.value);
        const response = await fetch(`${process.env.VUE_APP_API_URL}/games/team/${selectedTeam.value}`);
        if (!response.ok) {
          throw new Error('Failed to fetch games');
        }
        games.value = await response.json();
        console.log('Games received:', games.value);
      } catch (err) {
        error.value = err.message;
      }
    };

    const onTeamChange = async () => {
      console.log('Selected team:', selectedTeam.value);
      await fetchGames();
    };

    const getTeamDisplay = (game) => {
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

    const getResult = (game) => {
      const gameDate = new Date(game.game_date);
      const currentDate = new Date();

      // Check if the game date is in the future
      if (gameDate > currentDate) {
        return 'Scheduled'; // Return 'Scheduled' for future games
      }

      // Determine the result for past games
      const selectedTeamId = parseInt(selectedTeam.value);
      if (game.home_team_id === selectedTeamId) {
        return game.home_score > game.away_score ? 'W' : (game.home_score < game.away_score ? 'L' : 'T');
      } else if (game.away_team_id === selectedTeamId) {
        return game.away_score > game.home_score ? 'W' : (game.away_score < game.home_score ? 'L' : 'T');
      }
      return ''; // Return empty if the selected team is not involved in the game
    };

    // Calculate season statistics
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
        lastFive: []
      };

      // Sort games by date
      const sortedGames = [...games.value]
        .filter(game => new Date(game.game_date) <= currentDate)
        .sort((a, b) => new Date(a.game_date) - new Date(b.game_date));

      sortedGames.forEach((game) => {
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
          
          // Update Fall/Spring stats based on month
          if (isFall) {
            if (result === 'W') stats.fallWins++;
            else if (result === 'D') stats.fallDraws++;
            else stats.fallLosses++;
          } else {
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
      stats.points = (stats.wins * 3) + (stats.draws * 1);
      
      return stats;
    });

    onMounted(async () => {
      await fetchTeams();
      await fetchGames();
    });

    return {
      teams,
      games,
      selectedTeam,
      error,
      loading,
      onTeamChange,
      getResult,
      seasonStats,
      getTeamDisplay,
      getSelectedTeamName,
    };
  }
};
</script> 