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
          <option v-for="team in teams" :key="team.name" :value="team.name">{{ team.name }}</option>
        </select>
      </div>

      <!-- Display Filtered Games -->
      <div v-if="games.length > 0">
        <h3 class="text-lg font-semibold">Games for {{ selectedTeam }}</h3>
        <table class="min-w-full border border-gray-300">
          <thead>
            <tr>
              <th class="border-b text-right">#</th>
              <th class="border-b text-center">Date</th>
              <th class="border-b text-left">Home Team</th>
              <th class="border-b text-center">Score</th>
              <th class="border-b text-left">Away Team</th>
              <th class="border-b text-right">Result</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(game, index) in games" :key="game.game_date" :class="{'bg-gray-100': index % 2 === 0}">
              <td class="border-b text-right">{{ index + 1 }}</td>
              <td class="border-b text-center">{{ game.game_date }}</td>
              <td class="border-b text-left">{{ game.home_team }}</td>
              <td class="border-b text-center">{{ game.home_score }} - {{ game.away_score }}</td>
              <td class="border-b text-left">{{ game.away_team }}</td>
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
import { ref, onMounted } from 'vue';

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
        const response = await fetch('http://localhost:8000/api/teams');
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
        const response = await fetch(`http://localhost:8000/api/games/team/${selectedTeam.value}`);
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

    const getResult = (game) => {
      if (game.home_team === selectedTeam.value) {
        return game.home_score > game.away_score ? 'W' : (game.home_score < game.away_score ? 'L' : 'T');
      } else if (game.away_team === selectedTeam.value) {
        return game.away_score > game.home_score ? 'W' : (game.away_score < game.home_score ? 'L' : 'T');
      }
      return ''; // Return empty if the selected team is not involved in the game
    };

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
    };
  }
};
</script> 