<template>
  <div class="bg-white rounded-lg shadow p-4" data-testid="match-form">
    <!-- Form Type Selection -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2"
        >Action Type</label
      >
      <div class="flex space-x-4">
        <label class="inline-flex items-center">
          <input
            type="radio"
            v-model="formType"
            value="schedule"
            class="form-radio text-blue-600"
            data-testid="form-type-schedule"
          />
          <span class="ml-2">Schedule New Match</span>
        </label>
        <label class="inline-flex items-center">
          <input
            type="radio"
            v-model="formType"
            value="score"
            class="form-radio text-blue-600"
            data-testid="form-type-score"
          />
          <span class="ml-2">Score Match</span>
        </label>
      </div>
    </div>

    <form @submit.prevent="submitMatch" class="space-y-3">
      <!-- Season/Age Group/Match Type Row -->
      <div class="grid grid-cols-3 gap-3 p-3 bg-gray-50 rounded-md">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Season</label
          >
          <select
            v-model="selectedSeason"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="season-select"
          >
            <option
              v-for="season in activeSeasons"
              :key="season.id"
              :value="season.id"
            >
              {{ season.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Age Group</label
          >
          <select
            v-model="selectedAgeGroup"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="age-group-select"
          >
            <option
              v-for="ageGroup in ageGroups"
              :key="ageGroup.id"
              :value="ageGroup.id"
            >
              {{ ageGroup.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Match Type</label
          >
          <select
            v-model="selectedMatchType"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="match-type-select"
          >
            <option
              v-for="matchType in matchTypes"
              :key="matchType.id"
              :value="matchType.id"
            >
              {{ matchType.name }}
            </option>
          </select>
        </div>
      </div>

      <!-- Division Row (only for League matches) -->
      <div
        v-if="isLeagueMatch"
        class="p-3 bg-blue-50 rounded-md border border-blue-200"
        data-testid="division-section"
      >
        <div class="grid grid-cols-1 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1"
              >Division <span class="text-red-500">*</span></label
            >
            <select
              v-model="selectedDivision"
              class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
              required
              data-testid="division-select"
            >
              <option value="">Select Division</option>
              <option
                v-for="division in divisions"
                :key="division.id"
                :value="division.id"
              >
                {{ division.name }}
              </option>
            </select>
            <p class="text-xs text-gray-600 mt-1">
              Division is required for League matches to ensure proper standings
              calculation
            </p>
          </div>
        </div>
      </div>

      <!-- Game Status Row -->
      <div
        class="p-3 bg-green-50 rounded-md border border-green-200"
        data-testid="status-section"
      >
        <div class="grid grid-cols-1 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1"
              >Game Status <span class="text-red-500">*</span></label
            >
            <select
              v-model="selectedStatus"
              class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
              required
              data-testid="status-select"
            >
              <option value="scheduled">Scheduled</option>
              <option value="completed">Completed</option>
              <option value="postponed">Postponed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <p class="text-xs text-gray-600 mt-1">
              Status determines whether the match counts toward standings. Only
              "Completed" matches affect team standings.
            </p>
          </div>
        </div>
      </div>

      <!-- Date, Time, and Teams Row -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Date</label
          >
          <input
            type="date"
            v-model="matchData.date"
            id="match_date"
            required
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="date-input"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Kickoff Time
            <span class="text-gray-400 text-[10px]">(optional)</span></label
          >
          <input
            type="time"
            v-model="matchData.kickoffTime"
            id="kickoff_time"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="kickoff-time-input"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Home Team</label
          >
          <select
            v-model="matchData.homeTeam"
            id="home_team"
            required
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="home-team-select"
          >
            <option value="">Select Team</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Away Team</label
          >
          <select
            v-model="matchData.awayTeam"
            id="away_team"
            required
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            data-testid="away-team-select"
          >
            <option value="">Select Team</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }}
            </option>
          </select>
        </div>
      </div>

      <!-- Score Row (only show when scoring a match) -->
      <div
        v-if="formType === 'score'"
        class="flex items-center justify-center space-x-4 py-2"
        data-testid="score-section"
      >
        <div class="text-center">
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Home Score</label
          >
          <input
            type="number"
            v-model="matchData.homeScore"
            id="home_score"
            required
            min="0"
            class="block w-20 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-center text-lg font-bold"
            data-testid="home-score-input"
          />
        </div>

        <div class="text-xl font-bold text-gray-400">vs</div>

        <div class="text-center">
          <label class="block text-xs font-medium text-gray-700 mb-1"
            >Away Score</label
          >
          <input
            type="number"
            v-model="matchData.awayScore"
            id="away_score"
            required
            min="0"
            class="block w-20 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-center text-lg font-bold"
            data-testid="away-score-input"
          />
        </div>
      </div>

      <!-- Submit Button -->
      <div class="flex justify-end pt-2">
        <button
          type="submit"
          class="bg-blue-500 text-white px-4 py-1.5 rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 text-sm"
          data-testid="submit-button"
        >
          {{ formType === 'schedule' ? 'Schedule Game' : 'Submit Score' }}
        </button>
      </div>
    </form>

    <!-- Message Display -->
    <div
      v-if="message"
      class="mt-3 p-2 rounded-md text-sm"
      :class="{
        'bg-green-100 text-green-700': !error,
        'bg-red-100 text-red-700': error,
      }"
      data-testid="message"
    >
      {{ message }}
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

export default {
  name: 'MatchForm',
  setup() {
    const { apiRequest } = useAuthStore();
    const teams = ref([]);
    const error = ref(false);
    const message = ref('');
    const formType = ref('schedule');
    const matchData = ref({
      date: '',
      kickoffTime: '',
      homeTeam: '',
      awayTeam: '',
      homeScore: 0,
      awayScore: 0,
    });

    const activeSeasons = ref([]);
    const ageGroups = ref([]);
    const matchTypes = ref([]);
    const divisions = ref([]);
    const selectedSeason = ref(null);
    const selectedAgeGroup = ref(null);
    const selectedMatchType = ref(null);
    const selectedDivision = ref(null);
    const selectedStatus = ref('scheduled');

    // Computed property to check if current match type is League
    const isLeagueMatch = computed(() => {
      const leagueMatchType = matchTypes.value.find(gt => gt.name === 'League');
      return selectedMatchType.value === leagueMatchType?.id;
    });

    const fetchTeams = async () => {
      try {
        console.log('=== FETCHING TEAMS ===');
        console.log('Current selectedMatchType:', selectedMatchType.value);
        console.log('Current selectedAgeGroup:', selectedAgeGroup.value);
        console.log('Current selectedDivision:', selectedDivision.value);

        let url = `${getApiBaseUrl()}/api/teams`;

        // Add filtering if both match type and age group are selected
        if (selectedMatchType.value && selectedAgeGroup.value) {
          url += `?match_type_id=${selectedMatchType.value}&age_group_id=${selectedAgeGroup.value}`;

          // Add division filter for League matches when a division is selected
          if (isLeagueMatch.value && selectedDivision.value) {
            url += `&division_id=${selectedDivision.value}`;
          }

          console.log('Fetching filtered teams with URL:', url);
        } else {
          console.log('Fetching all teams (no filter)');
        }

        // Get auth token for authenticated requests
        const token = localStorage.getItem('auth_token');
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

        const response = await fetch(url, { headers: authHeaders });
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
        // Get auth token for authenticated requests
        const token = localStorage.getItem('auth_token');
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

        // Fetch active seasons (current and future)
        const activeSeasonsResponse = await fetch(
          `${getApiBaseUrl()}/api/active-seasons`,
          { headers: authHeaders }
        );
        if (activeSeasonsResponse.ok) {
          activeSeasons.value = await activeSeasonsResponse.json();
          // Default to first active season
          if (activeSeasons.value.length > 0) {
            selectedSeason.value = activeSeasons.value[0].id;
          }
        }

        // Fetch age groups
        const ageGroupsResponse = await fetch(
          `${getApiBaseUrl()}/api/age-groups`,
          { headers: authHeaders }
        );
        if (ageGroupsResponse.ok) {
          ageGroups.value = await ageGroupsResponse.json();
          // Default to U14
          selectedAgeGroup.value =
            ageGroups.value.find(ag => ag.name === 'U14')?.id ||
            ageGroups.value[0]?.id;
        }

        // Fetch match types
        const matchTypesResponse = await fetch(
          `${getApiBaseUrl()}/api/match-types`,
          { headers: authHeaders }
        );
        if (matchTypesResponse.ok) {
          matchTypes.value = await matchTypesResponse.json();
          // Default to League
          selectedMatchType.value =
            matchTypes.value.find(gt => gt.name === 'League')?.id ||
            matchTypes.value[0]?.id;
        }

        // Fetch divisions
        const divisionsResponse = await fetch(
          `${getApiBaseUrl()}/api/divisions`,
          { headers: authHeaders }
        );
        if (divisionsResponse.ok) {
          divisions.value = await divisionsResponse.json();
          // Default to Northeast for League matches
          if (divisions.value.length > 0) {
            selectedDivision.value =
              divisions.value.find(d => d.name === 'Northeast')?.id ||
              divisions.value[0]?.id;
          }
        }

        // After all defaults are set, fetch teams
        if (selectedMatchType.value && selectedAgeGroup.value) {
          await fetchTeams();
        }
      } catch (err) {
        console.error('Error fetching reference data:', err);
      }
    };

    const checkDuplicateMatch = async () => {
      try {
        const params = new URLSearchParams({
          date: matchData.value.date,
          homeTeam: matchData.value.homeTeam,
          awayTeam: matchData.value.awayTeam,
        });

        const response = await fetch(
          `${getApiBaseUrl()}/api/check-match?${params.toString()}`
        );

        if (!response.ok) {
          throw new Error('Failed to check for duplicate match');
        }

        const result = await response.json();
        return result;
      } catch (err) {
        console.error('Error checking for duplicate match:', err);
        return { exists: false }; // Fail open if we can't check
      }
    };

    // Convert local date + time to UTC ISO string for scheduled_kickoff
    const toScheduledKickoffUTC = (date, time) => {
      if (!date || !time) return null;
      // Combine date and time into a local datetime, then convert to UTC
      const localDateTime = new Date(`${date}T${time}`);
      return localDateTime.toISOString();
    };

    const submitMatch = async () => {
      console.log('Submitting match...');

      const matchDataToSubmit = {
        match_date: matchData.value.date,
        home_team_id: parseInt(matchData.value.homeTeam),
        away_team_id: parseInt(matchData.value.awayTeam),
        home_score: matchData.value.homeScore,
        away_score: matchData.value.awayScore,
        season_id: selectedSeason.value,
        age_group_id: selectedAgeGroup.value,
        match_type_id: selectedMatchType.value,
        status: selectedStatus.value,
        scheduled_kickoff: toScheduledKickoffUTC(
          matchData.value.date,
          matchData.value.kickoffTime
        ),
      };

      // Add division_id for League matches
      const leagueMatchType = matchTypes.value.find(gt => gt.name === 'League');
      if (selectedMatchType.value === leagueMatchType?.id) {
        if (!selectedDivision.value) {
          message.value = 'Division is required for League matches';
          error.value = true;
          return;
        }
        matchDataToSubmit.division_id = selectedDivision.value;
      }

      console.log('Match Data before stringification:', matchDataToSubmit);
      const requestBody = JSON.stringify(matchDataToSubmit);
      console.log('Request Body (JSON):', requestBody);

      error.value = false;
      message.value = '';

      // Validate teams are different
      if (matchData.value.homeTeam === matchData.value.awayTeam) {
        message.value = 'Home and Away teams cannot be the same';
        error.value = true;
        return;
      }

      // Validate required IDs are available
      if (
        !selectedSeason.value ||
        !selectedAgeGroup.value ||
        !selectedMatchType.value
      ) {
        message.value =
          'Missing required data. Please try refreshing the page.';
        error.value = true;
        return;
      }

      // Check for existing match
      const matchCheck = await checkDuplicateMatch();

      if (formType.value === 'schedule') {
        // When scheduling, prevent duplicates
        if (matchCheck.exists) {
          message.value = 'This match is already scheduled for this date';
          error.value = true;
          return;
        }
      }

      try {
        let result;

        if (
          formType.value === 'score' &&
          matchCheck.exists &&
          matchCheck.match_id
        ) {
          // Update existing match
          result = await apiRequest(
            `${getApiBaseUrl()}/api/matches/${matchCheck.match_id}`,
            {
              method: 'PUT',
              body: requestBody,
            }
          );
        } else {
          // Create new match
          result = await apiRequest(`${getApiBaseUrl()}/api/matches`, {
            method: 'POST',
            body: requestBody,
          });
        }

        if (result) {
          message.value =
            formType.value === 'schedule'
              ? 'Match scheduled successfully'
              : matchCheck.exists
                ? 'Score updated successfully'
                : 'Score submitted successfully';
          error.value = false;
          // Reset form
          matchData.value = {
            date: '',
            kickoffTime: '',
            homeTeam: '',
            awayTeam: '',
            homeScore: 0,
            awayScore: 0,
          };
          formType.value = 'schedule';
        } else {
          message.value = result.detail || 'Error submitting match';
          error.value = true;
        }
      } catch (err) {
        console.error('Error submitting match:', err);
        message.value = 'Error submitting match';
        error.value = true;
      }
    };

    // Watch for changes in match type, age group, or division to refetch teams
    watch(
      [selectedMatchType, selectedAgeGroup, selectedDivision],
      async (newValues, oldValues) => {
        console.log('=== WATCHER TRIGGERED ===');
        console.log('New values:', newValues);
        console.log('Old values:', oldValues);
        console.log('selectedMatchType.value:', selectedMatchType.value);
        console.log('selectedAgeGroup.value:', selectedAgeGroup.value);
        console.log('selectedDivision.value:', selectedDivision.value);

        if (selectedMatchType.value && selectedAgeGroup.value) {
          console.log('Match type and age group are set, fetching teams...');
          await fetchTeams();
          // Reset team selections when filter changes
          console.log('Resetting team selections');
          matchData.value.homeTeam = '';
          matchData.value.awayTeam = '';
        } else {
          console.log('Match type or age group not set, skipping team fetch');
        }
        console.log('=== END WATCHER ===');
      }
    );

    // Watch for changes in match type to handle division requirements
    watch(selectedMatchType, newMatchType => {
      const leagueMatchType = matchTypes.value.find(gt => gt.name === 'League');
      if (newMatchType === leagueMatchType?.id) {
        // Auto-select Northeast division for League matches if available
        if (divisions.value.length > 0 && !selectedDivision.value) {
          selectedDivision.value =
            divisions.value.find(d => d.name === 'Northeast')?.id ||
            divisions.value[0]?.id;
        }
      } else {
        // Clear division for non-League matches
        selectedDivision.value = null;
      }
    });

    onMounted(async () => {
      await fetchReferenceData();
    });

    return {
      teams,
      matchData,
      message,
      error,
      formType,
      submitMatch,
      checkDuplicateMatch,
      activeSeasons,
      ageGroups,
      matchTypes,
      divisions,
      selectedSeason,
      selectedAgeGroup,
      selectedMatchType,
      selectedDivision,
      selectedStatus,
      isLeagueMatch,
    };
  },
};
</script>
