<template>
  <div class="bg-white rounded-lg shadow p-4">
    <!-- Form Type Selection -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">Action Type</label>
      <div class="flex space-x-4">
        <label class="inline-flex items-center">
          <input 
            type="radio" 
            v-model="formType" 
            value="schedule" 
            class="form-radio text-blue-600"
          />
          <span class="ml-2">Schedule New Game</span>
        </label>
        <label class="inline-flex items-center">
          <input 
            type="radio" 
            v-model="formType" 
            value="score" 
            class="form-radio text-blue-600"
          />
          <span class="ml-2">Score Game</span>
        </label>
      </div>
    </div>

    <form @submit.prevent="submitGame" class="space-y-3">
      <!-- Season/Age Group/Game Type Row -->
      <div class="grid grid-cols-3 gap-3 p-3 bg-gray-50 rounded-md">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Season</label>
          <select 
            v-model="selectedSeason" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option v-for="season in activeSeasons" :key="season.id" :value="season.id">
              {{ season.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Age Group</label>
          <select 
            v-model="selectedAgeGroup" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option v-for="ageGroup in ageGroups" :key="ageGroup.id" :value="ageGroup.id">
              {{ ageGroup.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Game Type</label>
          <select 
            v-model="selectedGameType" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option v-for="gameType in gameTypes" :key="gameType.id" :value="gameType.id">
              {{ gameType.name }}
            </option>
          </select>
        </div>
      </div>

      <!-- Date and Teams Row -->
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Date</label>
          <input 
            type="date" 
            v-model="gameData.date"
            id="game_date" 
            required
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Home Team</label>
          <select 
            v-model="gameData.homeTeam" 
            id="home_team"
            required
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option value="">Select Team</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">{{ team.name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Away Team</label>
          <select 
            v-model="gameData.awayTeam" 
            id="away_team"
            required
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option value="">Select Team</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">{{ team.name }}</option>
          </select>
        </div>
      </div>

      <!-- Score Row (only show when scoring a game) -->
      <div v-if="formType === 'score'" class="flex items-center justify-center space-x-4 py-2">
        <div class="text-center">
          <label class="block text-xs font-medium text-gray-700 mb-1">Home Score</label>
          <input 
            type="number" 
            v-model="gameData.homeScore" 
            id="home_score"
            required
            min="0"
            class="block w-20 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-center text-lg font-bold"
          />
        </div>

        <div class="text-xl font-bold text-gray-400">vs</div>

        <div class="text-center">
          <label class="block text-xs font-medium text-gray-700 mb-1">Away Score</label>
          <input 
            type="number" 
            v-model="gameData.awayScore" 
            id="away_score"
            required
            min="0"
            class="block w-20 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-center text-lg font-bold"
          />
        </div>
      </div>

      <!-- Submit Button -->
      <div class="flex justify-end pt-2">
        <button 
          type="submit"
          class="bg-blue-500 text-white px-4 py-1.5 rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 text-sm"
        >
          {{ formType === 'schedule' ? 'Schedule Game' : 'Submit Score' }}
        </button>
      </div>
    </form>

    <!-- Message Display -->
    <div 
      v-if="message" 
      class="mt-3 p-2 rounded-md text-sm"
      :class="{'bg-green-100 text-green-700': !error, 'bg-red-100 text-red-700': error}"
    >
      {{ message }}
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'

export default {
  name: 'GameForm',
  setup() {
    const teams = ref([]);
    const error = ref(false);
    const message = ref('');
    const formType = ref('schedule');
    const gameData = ref({
      date: '',
      homeTeam: '',
      awayTeam: '',
      homeScore: 0,
      awayScore: 0
    });

    const activeSeasons = ref([]);
    const ageGroups = ref([]);
    const gameTypes = ref([]);
    const selectedSeason = ref(null);
    const selectedAgeGroup = ref(null);
    const selectedGameType = ref(null);

    const fetchTeams = async () => {
      try {
        console.log('=== FETCHING TEAMS ===');
        console.log('Current selectedGameType:', selectedGameType.value);
        console.log('Current selectedAgeGroup:', selectedAgeGroup.value);
        
        let url = 'http://localhost:8000/api/teams';
        
        // Add filtering if both game type and age group are selected
        if (selectedGameType.value && selectedAgeGroup.value) {
          url += `?game_type_id=${selectedGameType.value}&age_group_id=${selectedAgeGroup.value}`;
          console.log('Fetching filtered teams with URL:', url);
        } else {
          console.log('Fetching all teams (no filter)');
        }
        
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch teams');
        const data = await response.json();
        console.log('Teams received count:', data.length);
        console.log('Team names:', data.map(t => t.name).sort());
        console.log('Previous teams count:', teams.value.length);
        
        teams.value = data;
        console.log('Teams updated, new count:', teams.value.length);
        console.log('=== END FETCHING TEAMS ===');
      } catch (err) {
        console.error('Error fetching teams:', err);
        message.value = 'Error loading teams';
        error.value = true;
      }
    };

    const fetchReferenceData = async () => {
      try {
        // Fetch active seasons (current and future)
        const activeSeasonsResponse = await fetch('http://localhost:8000/api/active-seasons');
        if (activeSeasonsResponse.ok) {
          activeSeasons.value = await activeSeasonsResponse.json();
          // Default to first active season
          if (activeSeasons.value.length > 0) {
            selectedSeason.value = activeSeasons.value[0].id;
          }
        }

        // Fetch age groups
        const ageGroupsResponse = await fetch('http://localhost:8000/api/age-groups');
        if (ageGroupsResponse.ok) {
          ageGroups.value = await ageGroupsResponse.json();
          // Default to U14
          selectedAgeGroup.value = ageGroups.value.find(ag => ag.name === 'U14')?.id || ageGroups.value[0]?.id;
        }

        // Fetch game types
        const gameTypesResponse = await fetch('http://localhost:8000/api/game-types');
        if (gameTypesResponse.ok) {
          gameTypes.value = await gameTypesResponse.json();
          // Default to League
          selectedGameType.value = gameTypes.value.find(gt => gt.name === 'League')?.id || gameTypes.value[0]?.id;
        }

        // After all defaults are set, fetch teams
        if (selectedGameType.value && selectedAgeGroup.value) {
          await fetchTeams();
        }
      } catch (err) {
        console.error('Error fetching reference data:', err);
      }
    };

    const checkDuplicateGame = async () => {
      try {
        const params = new URLSearchParams({
          date: gameData.value.date,
          homeTeam: gameData.value.homeTeam,
          awayTeam: gameData.value.awayTeam
        });

        const response = await fetch(`http://localhost:8000/api/check-game?${params.toString()}`);
        
        if (!response.ok) {
          throw new Error('Failed to check for duplicate game');
        }

        const result = await response.json();
        return result.exists;
      } catch (err) {
        console.error('Error checking for duplicate game:', err);
        return false; // Fail open if we can't check
      }
    };

    const submitGame = async () => {
      console.log('Submitting game...');

      const gameDataToSubmit = {
        game_date: gameData.value.date,
        home_team_id: parseInt(gameData.value.homeTeam),
        away_team_id: parseInt(gameData.value.awayTeam),
        home_score: gameData.value.homeScore,
        away_score: gameData.value.awayScore,
        season_id: selectedSeason.value,
        age_group_id: selectedAgeGroup.value,
        game_type_id: selectedGameType.value
      };

      console.log('Game Data before stringification:', gameDataToSubmit);
      const requestBody = JSON.stringify(gameDataToSubmit);
      console.log('Request Body (JSON):', requestBody);

      error.value = false;
      message.value = '';

      // Validate teams are different
      if (gameData.value.homeTeam === gameData.value.awayTeam) {
        message.value = 'Home and Away teams cannot be the same';
        error.value = true;
        return;
      }

      // Validate required IDs are available
      if (!selectedSeason.value || !selectedAgeGroup.value || !selectedGameType.value) {
        message.value = 'Missing required data. Please try refreshing the page.';
        error.value = true;
        return;
      }

      // Check for duplicate game when scheduling
      if (formType.value === 'schedule') {
        const isDuplicate = await checkDuplicateGame();
        if (isDuplicate) {
          message.value = 'This game is already scheduled for this date';
          error.value = true;
          return;
        }
      }

      try {
        const response = await fetch('http://localhost:8000/api/games', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: requestBody
        });

        const result = await response.json();
        
        if (response.ok) {
          message.value = formType.value === 'schedule' 
            ? 'Game scheduled successfully' 
            : 'Score submitted successfully';
          error.value = false;
          // Reset form
          gameData.value = {
            date: '',
            homeTeam: '',
            awayTeam: '',
            homeScore: 0,
            awayScore: 0
          };
          formType.value = 'schedule';
        } else {
          message.value = result.detail || 'Error submitting game';
          error.value = true;
        }
      } catch (err) {
        console.error('Error submitting game:', err);
        message.value = 'Error submitting game';
        error.value = true;
      }
    };

    // Watch for changes in game type or age group to refetch teams
    watch([selectedGameType, selectedAgeGroup], async (newValues, oldValues) => {
      console.log('=== WATCHER TRIGGERED ===');
      console.log('New values:', newValues);
      console.log('Old values:', oldValues);
      console.log('selectedGameType.value:', selectedGameType.value);
      console.log('selectedAgeGroup.value:', selectedAgeGroup.value);
      
      if (selectedGameType.value && selectedAgeGroup.value) {
        console.log('Both game type and age group are set, fetching teams...');
        await fetchTeams();
        // Reset team selections when filter changes
        console.log('Resetting team selections');
        gameData.value.homeTeam = '';
        gameData.value.awayTeam = '';
      } else {
        console.log('Game type or age group not set, skipping team fetch');
      }
      console.log('=== END WATCHER ===');
    });

    onMounted(async () => {
      await fetchReferenceData();
    });

    return {
      teams,
      gameData,
      message,
      error,
      formType,
      submitGame,
      checkDuplicateGame,
      activeSeasons,
      ageGroups,
      gameTypes,
      selectedSeason,
      selectedAgeGroup,
      selectedGameType
    };    
  }
}
</script>