<template>
  <div>
    <!-- Loading State -->
    <div v-if="loading" class="text-center py-4">
      Loading teams and matches...
    </div>

    <!-- Error State -->
    <div v-if="error" class="text-red-600 p-4 mb-4">Error: {{ error }}</div>

    <div v-else>
      <!-- Filters Section -->
      <div class="mb-6">
        <!-- Mobile: Collapsible Filters -->
        <div class="lg:hidden mb-4">
          <button
            @click="showFilters = !showFilters"
            class="w-full flex items-center justify-between px-4 py-3 bg-blue-600 text-white rounded-lg font-medium"
          >
            <span>Filters</span>
            <svg
              :class="[
                'w-5 h-5 transition-transform',
                showFilters ? 'rotate-180' : '',
              ]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
        </div>

        <!-- Filters Content -->
        <div :class="['space-y-4', showFilters || 'hidden lg:block']">
          <!-- Team Filter - Most Important, Always Visible -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >Select Team</label
            >
            <select
              v-model="selectedTeam"
              @change="onTeamChange"
              class="block w-full px-4 py-3 text-base border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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

          <!-- Age Group Filter -->
          <div>
            <h3 class="text-sm font-medium text-gray-700 mb-2">Age Groups</h3>
            <div
              class="grid grid-cols-2 sm:grid-cols-3 lg:flex lg:flex-wrap gap-2"
            >
              <button
                v-for="ageGroup in filteredAgeGroups"
                :key="ageGroup.id"
                @click="selectedAgeGroupId = ageGroup.id"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  selectedAgeGroupId === ageGroup.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300',
                ]"
              >
                {{ ageGroup.name }}
              </button>
            </div>
          </div>

          <!-- Season Dropdown -->
          <div>
            <h3 class="text-sm font-medium text-gray-700 mb-2">Season</h3>
            <select
              v-model="selectedSeasonId"
              class="block w-full px-4 py-3 text-base border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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

          <!-- Match Type Filter -->
          <div>
            <h3 class="text-sm font-medium text-gray-700 mb-2">Match Type</h3>
            <div
              class="grid grid-cols-2 sm:grid-cols-3 lg:flex lg:flex-wrap gap-2"
            >
              <button
                @click="selectedMatchTypeId = 1"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  selectedMatchTypeId === 1
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300',
                ]"
              >
                League
              </button>
              <button
                @click="selectedMatchTypeId = 3"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  selectedMatchTypeId === 3
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300',
                ]"
              >
                Friendly
              </button>
              <button
                @click="selectedMatchTypeId = 2"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  selectedMatchTypeId === 2
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300',
                ]"
              >
                Tournament
              </button>
              <button
                @click="selectedMatchTypeId = 4"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  selectedMatchTypeId === 4
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300',
                ]"
              >
                Playoff
              </button>
              <button
                @click="selectedMatchTypeId = null"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  selectedMatchTypeId === null
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300',
                ]"
              >
                All Matches
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Display Filtered Matchs -->
      <div v-if="sortedGames.length > 0">
        <div class="mb-4">
          <h3 class="text-lg font-semibold mb-2">
            Matchs for {{ getSelectedTeamName() }}
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
        <div class="mb-4 space-y-3">
          <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h4 class="font-medium text-gray-700 mb-3">Season Summary</h4>
            <div class="grid grid-cols-4 sm:grid-cols-8 gap-3 text-sm">
              <div class="font-medium">GP: {{ seasonStats.matchesPlayed }}</div>
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

          <!-- Season Segments - Stack on mobile -->
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <!-- Fall Segment - Only show if Fall matches exist -->
            <div
              v-if="seasonStats.hasFallGames"
              class="p-4 bg-blue-50 rounded-lg border border-blue-100"
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
                <div class="col-span-3 text-xs text-gray-500 mt-1">
                  Aug - Dec matches
                </div>
              </div>
            </div>

            <!-- Spring Segment - Only show if Spring matches exist -->
            <div
              v-if="seasonStats.hasSpringGames"
              class="p-4 bg-green-50 rounded-lg border border-green-100"
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
                <div class="col-span-3 text-xs text-gray-500 mt-1">
                  Jan - July matches
                </div>
              </div>
            </div>

            <!-- Last 5 Matchs - Only show if matches exist -->
            <div
              v-if="seasonStats.matchesPlayed > 0"
              class="p-4 bg-purple-50 rounded-lg border border-purple-100"
            >
              <h4 class="font-medium text-purple-700 mb-2">Last 5 Matchs</h4>
              <div class="flex space-x-2 justify-center sm:justify-start">
                <template v-if="seasonStats.lastFive.length > 0">
                  <span
                    v-for="(result, index) in seasonStats.lastFive"
                    :key="index"
                    class="w-8 h-8 flex items-center justify-center rounded-full text-sm font-medium"
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
                  >No recent matches</span
                >
              </div>
            </div>
          </div>
        </div>

        <!-- Desktop: Table View -->
        <table class="hidden lg:table w-full border border-gray-300">
          <thead>
            <tr>
              <th class="border-b text-right w-12">#</th>
              <th class="border-b text-center w-32">Date</th>
              <th class="border-b text-left px-2">Team</th>
              <th class="border-b text-center w-24">Score</th>
              <th class="border-b text-center w-20">Result</th>
              <th class="border-b text-center w-24">Match Type</th>
              <th class="border-b text-center w-24">Status</th>
              <th class="border-b text-center w-32">Match ID</th>
              <th class="border-b text-center w-16">Source</th>
              <th v-if="canEditGames" class="border-b text-center w-24">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(match, index) in sortedGames"
              :key="match.id"
              :class="{ 'bg-gray-100': index % 2 === 0 }"
            >
              <td class="border-b text-right">{{ index + 1 }}</td>
              <td class="border-b text-center">{{ match.match_date }}</td>
              <td class="border-b text-left px-2">
                {{ getTeamDisplay(match) }}
              </td>
              <td class="border-b text-center">
                {{ getScoreDisplay(match) }}
              </td>
              <td class="border-b text-center">
                <span
                  v-if="match.match_status === 'played'"
                  class="px-2 py-1 rounded-full text-sm font-bold"
                  :class="{
                    'bg-green-100 text-green-800': getResult(match) === 'W',
                    'bg-yellow-100 text-yellow-800': getResult(match) === 'T',
                    'bg-red-100 text-red-800': getResult(match) === 'L',
                  }"
                >
                  {{ getResult(match) }}
                </span>
                <span v-else class="text-gray-400">-</span>
              </td>
              <td class="border-b text-center">
                {{ match.match_type_name || 'League' }}
              </td>
              <td class="border-b text-center">
                <span
                  :class="{
                    'px-2 py-1 rounded text-xs font-medium': true,
                    'bg-green-100 text-green-800':
                      match.match_status === 'played',
                    'bg-blue-100 text-blue-800':
                      match.match_status === 'scheduled',
                    'bg-yellow-100 text-yellow-800':
                      match.match_status === 'postponed',
                    'bg-red-100 text-red-800':
                      match.match_status === 'cancelled',
                    'bg-gray-100 text-gray-800': !match.match_status,
                  }"
                >
                  {{ match.match_status || 'scheduled' }}
                </span>
              </td>
              <td class="border-b text-center">
                <span
                  v-if="match.match_id"
                  class="text-xs font-mono text-gray-700"
                  :title="`External Match ID: ${match.match_id}`"
                >
                  {{ match.match_id }}
                </span>
                <span v-else class="text-gray-400 text-xs">-</span>
              </td>
              <td class="border-b text-center">
                <span
                  :title="getSourceTooltip(match)"
                  :class="{
                    'px-2 py-1 rounded text-xs font-medium': true,
                    'bg-purple-100 text-purple-800':
                      match.source === 'match-scraper',
                    'bg-gray-100 text-gray-700': match.source === 'manual',
                    'bg-yellow-100 text-yellow-700': match.source === 'import',
                  }"
                >
                  {{ getSourceDisplay(match.source) }}
                </span>
              </td>
              <td v-if="canEditGames" class="border-b text-center">
                <button
                  v-if="canEditGame(match)"
                  @click="editMatch(match)"
                  class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  Edit
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Mobile: Card View -->
        <div class="lg:hidden space-y-3">
          <div
            v-for="(match, index) in sortedGames"
            :key="match.id"
            class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
          >
            <!-- Match Number and Date -->
            <div
              class="flex items-center justify-between mb-3 pb-3 border-b border-gray-100"
            >
              <span class="text-xs font-medium text-gray-500"
                >Game #{{ index + 1 }}</span
              >
              <span class="text-sm font-medium text-gray-700">{{
                match.match_date
              }}</span>
            </div>

            <!-- Teams and Score -->
            <div class="mb-3">
              <div class="text-base font-medium text-gray-900 mb-2">
                {{ getTeamDisplay(match) }}
              </div>
              <div class="flex items-center space-x-3">
                <span class="text-2xl font-bold text-gray-900">
                  {{ getScoreDisplay(match) }}
                </span>
                <span
                  v-if="match.match_status === 'played'"
                  class="px-3 py-1 rounded-full text-sm font-bold"
                  :class="{
                    'bg-green-100 text-green-800': getResult(match) === 'W',
                    'bg-yellow-100 text-yellow-800': getResult(match) === 'T',
                    'bg-red-100 text-red-800': getResult(match) === 'L',
                  }"
                >
                  {{ getResult(match) }}
                </span>
              </div>
            </div>

            <!-- Match Details -->
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span class="text-gray-500">Type:</span>
                <span class="ml-1 font-medium">{{
                  match.match_type_name || 'League'
                }}</span>
              </div>
              <div>
                <span class="text-gray-500">Status:</span>
                <span
                  class="ml-1 px-2 py-0.5 rounded text-xs font-medium"
                  :class="{
                    'bg-green-100 text-green-800':
                      match.match_status === 'played',
                    'bg-blue-100 text-blue-800':
                      match.match_status === 'scheduled',
                    'bg-yellow-100 text-yellow-800':
                      match.match_status === 'postponed',
                    'bg-red-100 text-red-800':
                      match.match_status === 'cancelled',
                    'bg-gray-100 text-gray-800': !match.match_status,
                  }"
                >
                  {{ match.match_status || 'scheduled' }}
                </span>
              </div>
              <div v-if="match.match_id">
                <span class="text-gray-500">Match ID:</span>
                <span class="ml-1 font-mono text-xs">{{ match.match_id }}</span>
              </div>
              <div>
                <span class="text-gray-500">Source:</span>
                <span class="ml-1" :title="getSourceTooltip(match)">
                  {{ getSourceDisplay(match.source) }}
                </span>
              </div>
              <div v-if="canEditGames && canEditGame(match)" class="text-right">
                <button
                  @click="editMatch(match)"
                  class="text-blue-600 font-medium text-sm active:text-blue-800"
                >
                  Edit
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else>
        <p class="text-center text-gray-500 py-8">
          No matches found for the selected team.
        </p>
      </div>
    </div>

    <!-- Match Edit Modal -->
    <MatchEditModal
      :show="showEditModal"
      :game="editingMatch"
      :teams="teams"
      :seasons="seasons"
      :match-types="matchTypes"
      :age-groups="ageGroups"
      @close="closeEditModal"
      @updated="onGameUpdated"
    />
  </div>
</template>

<script>
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import MatchEditModal from '@/components/MatchEditModal.vue';

export default {
  name: 'MatchesView',
  components: {
    MatchEditModal,
  },
  setup() {
    const authStore = useAuthStore();
    const teams = ref([]);
    const matches = ref([]);
    const ageGroups = ref([]);
    const seasons = ref([]);
    const matchTypes = ref([]);
    const selectedTeam = ref('');
    const selectedAgeGroupId = ref(2); // Default to U14
    const selectedSeasonId = ref(3); // Default to 2025-2026
    const selectedMatchTypeId = ref(1); // Default to League matches (id: 1)
    const error = ref(null);
    const loading = ref(true);
    const showEditModal = ref(false);
    const editingMatch = ref(null);
    const showFilters = ref(true); // Filters visible by default on mobile

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
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/match-types`
        );
        if (!response.ok) throw new Error('Failed to fetch match types');
        matchTypes.value = await response.json();
      } catch (err) {
        console.error('Error fetching match types:', err);
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
            // Fetch matches for the player's team
            await fetchMatches();
          }
        }
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchMatches = async () => {
      // Guard against unauthorized access
      if (!authStore.isAuthenticated.value) {
        console.warn('User not authenticated, cannot fetch matches');
        return;
      }

      if (!selectedTeam.value) {
        console.log('No team selected, skipping fetch.');
        matches.value = []; // Clear matches if no team is selected
        return; // Exit the function early
      }

      try {
        console.log(
          'Fetching matches for team:',
          selectedTeam.value,
          'season:',
          selectedSeasonId.value
        );
        const url = `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/matches/team/${selectedTeam.value}?season_id=${selectedSeasonId.value}`;
        matches.value = await authStore.apiRequest(url);
        console.log('Games received:', matches.value);
      } catch (err) {
        error.value = err.message;
      }
    };

    const onTeamChange = async () => {
      console.log('Selected team:', selectedTeam.value);
      await fetchMatches();
    };

    const getTeamDisplay = match => {
      const selectedTeamId = parseInt(selectedTeam.value);
      if (match.home_team_id === selectedTeamId) {
        return `vs ${match.away_team_name}`;
      } else {
        return `@ ${match.home_team_name}`;
      }
    };

    const getSelectedTeamName = () => {
      const team = teams.value.find(t => t.id === parseInt(selectedTeam.value));
      return team ? team.name : 'Selected Team';
    };

    const getScoreDisplay = match => {
      // Only show scores for matches that have been played
      if (match.match_status !== 'played') {
        return '-'; // Return dash for matches not yet played
      }
      return `${match.home_score} - ${match.away_score}`;
    };

    const getSourceDisplay = source => {
      if (!source || source === 'manual') return '✏️';
      if (source === 'match-scraper') return '🤖';
      if (source === 'import') return '📥';
      return '?';
    };

    const getSourceTooltip = match => {
      const source = match.source || 'manual';
      const sourceText =
        {
          manual: 'Manually entered',
          'match-scraper': 'Auto-scraped from official source',
          import: 'Imported from backup',
        }[source] || 'Unknown source';

      if (match.updated_at) {
        const date = new Date(match.updated_at).toLocaleDateString();
        return `${sourceText} • Last updated: ${date}`;
      }
      return sourceText;
    };

    const getResult = match => {
      // Only show results for matches that have been played
      if (match.match_status !== 'played') {
        return '-'; // Return dash for matches not yet played
      }

      // Determine the result for played matches
      const selectedTeamId = parseInt(selectedTeam.value);
      if (match.home_team_id === selectedTeamId) {
        return match.home_score > match.away_score
          ? 'W'
          : match.home_score < match.away_score
            ? 'L'
            : 'T';
      } else if (match.away_team_id === selectedTeamId) {
        return match.away_score > match.home_score
          ? 'W'
          : match.away_score < match.home_score
            ? 'L'
            : 'T';
      }
      return ''; // Return empty if the selected team is not involved in the match
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
        (seasonStats.value.matchesPlayed > 0 ? 1 : 0);

      if (segmentCount <= 1) return 'grid-cols-1';
      if (segmentCount === 2) return 'grid-cols-1 md:grid-cols-2';
      return 'grid-cols-1 md:grid-cols-3';
    };

    // Filter age groups to only show those that have teams
    const filteredAgeGroups = computed(() => {
      // Get unique age group IDs from teams
      const teamAgeGroupIds = new Set();
      teams.value.forEach(team => {
        if (team.age_groups && Array.isArray(team.age_groups)) {
          team.age_groups.forEach(ag => teamAgeGroupIds.add(ag.id));
        }
      });

      // Filter age groups to only those with teams
      return ageGroups.value.filter(ag => teamAgeGroupIds.has(ag.id));
    });

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

    // Sort matches by date in ascending order for display and filter by match type
    const sortedGames = computed(() => {
      // Filter out any undefined/null items and ensure match_date exists
      let filteredGames = [...matches.value].filter(
        match => match && match.match_date
      );

      // Filter by match type if a specific type is selected (not "All Matches")
      if (selectedMatchTypeId.value !== null) {
        filteredGames = filteredGames.filter(
          match => match.match_type_id === selectedMatchTypeId.value
        );
      }

      return filteredGames.sort(
        (a, b) => new Date(a.match_date) - new Date(b.match_date)
      );
    });

    // Calculate season statistics based on selected match type filter
    const seasonStats = computed(() => {
      const currentDate = new Date();
      const stats = {
        matchesPlayed: 0,
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

      // Sort matches by date (ascending order) and filter by selected match type
      let sortedGames = [...matches.value].filter(
        match => new Date(match.match_date) <= currentDate
      );

      // Apply match type filter if a specific type is selected
      if (selectedMatchTypeId.value !== null) {
        sortedGames = sortedGames.filter(
          match => match.match_type_id === selectedMatchTypeId.value
        );
      }

      sortedGames = sortedGames.sort(
        (a, b) => new Date(a.match_date) - new Date(b.match_date)
      );

      sortedGames.forEach(match => {
        const selectedTeamId = parseInt(selectedTeam.value);
        const isHome = match.home_team_id === selectedTeamId;
        const isAway = match.away_team_id === selectedTeamId;

        if (isHome || isAway) {
          const teamScore = isHome ? match.home_score : match.away_score;
          const opponentScore = isHome ? match.away_score : match.home_score;

          // Basic stats
          stats.matchesPlayed++;
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

          // Determine if match is in Fall or Spring segment based on month
          const matchDate = new Date(match.match_date);
          const month = String(matchDate.getMonth() + 1).padStart(2, '0');
          const isFall = ['08', '09', '10', '11', '12'].includes(month);

          // Track that matches exist in these periods
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

          // Track last 5 matches (will be reversed later to show most recent first)
          if (stats.lastFive.length < 5) {
            stats.lastFive.push(result);
          }
        }
      });

      // Reverse lastFive to show most recent matches first
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
      matches.value = []; // Clear matches
    });

    // Watch for team changes to fetch matches
    watch(selectedTeam, () => {
      fetchMatches();
    });

    // Watch for season changes to refetch matches if team is selected
    watch(selectedSeasonId, () => {
      if (selectedTeam.value) {
        fetchMatches();
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

    const canEditGame = match => {
      // Admins can edit all matches
      if (authStore.isAdmin) {
        return true;
      }

      // Team managers can only edit matches involving their team
      if (authStore.isTeamManager && authStore.userTeamId) {
        return (
          match.home_team_id === authStore.userTeamId ||
          match.away_team_id === authStore.userTeamId
        );
      }

      return false;
    };

    const editMatch = match => {
      editingMatch.value = match;
      showEditModal.value = true;
    };

    const closeEditModal = () => {
      showEditModal.value = false;
      editingMatch.value = null;
    };

    const onGameUpdated = () => {
      // Refresh the matches list after a successful update
      fetchMatches();
    };

    onMounted(async () => {
      // Only fetch data if user is authenticated
      if (!authStore.isAuthenticated.value) {
        console.warn('User not authenticated, skipping data fetch');
        loading.value = false;
        error.value = 'Please log in to view matches';
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
      matches,
      sortedGames,
      ageGroups,
      filteredAgeGroups,
      seasons,
      matchTypes,
      selectedTeam,
      selectedAgeGroupId,
      selectedSeasonId,
      selectedMatchTypeId,
      filteredTeams,
      selectedTeamLeagueInfo,
      selectedSeasonName,
      error,
      loading,
      showFilters,
      onTeamChange,
      getScoreDisplay,
      getSourceDisplay,
      getSourceTooltip,
      getResult,
      seasonStats,
      getTeamDisplay,
      getSelectedTeamName,
      formatSeasonDates,
      getSegmentGridClass,
      canEditGames,
      canEditGame,
      editMatch,
      closeEditModal,
      onGameUpdated,
      showEditModal,
      editingMatch,
    };
  },
};
</script>
