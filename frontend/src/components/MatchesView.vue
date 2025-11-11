<template>
  <div>
    <!-- Loading State -->
    <div v-if="loading" class="text-center py-4">
      Loading teams and matches...
    </div>

    <!-- Error State -->
    <div v-if="error" class="text-red-600 p-4 mb-4">Error: {{ error }}</div>

    <div v-else>
      <!-- View Tabs: All Matches vs My Club -->
      <div class="mb-6 border-b border-gray-200">
        <nav class="flex space-x-4" aria-label="Match view tabs">
          <button
            @click="selectedViewTab = 'all'"
            :class="[
              'py-3 px-4 text-sm font-medium border-b-2 transition-colors',
              selectedViewTab === 'all'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
            ]"
          >
            All Matches
          </button>
          <button
            @click="selectedViewTab = 'myclub'"
            :class="[
              'py-3 px-4 text-sm font-medium border-b-2 transition-colors',
              selectedViewTab === 'myclub'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
            ]"
          >
            My Club
          </button>
        </nav>
      </div>

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
          <!-- My Club Filters - Only show on My Club tab -->
          <div v-if="selectedViewTab === 'myclub'" class="space-y-4">
            <!-- League Selector - Only for admins -->
            <div v-if="authStore.isAdmin.value">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Select League</label
              >
              <select
                v-model="selectedLeagueId"
                class="block w-full px-4 py-3 text-base border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option :value="null">-- Select a league --</option>
                <option
                  v-for="league in leagues"
                  :key="league.id"
                  :value="league.id"
                >
                  {{ league.name }}
                </option>
              </select>
            </div>

            <!-- League Display - For non-admins (read-only) -->
            <div v-else-if="userLeagueInfo">
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >League</label
              >
              <div
                class="block w-full px-4 py-3 text-base bg-gray-50 border border-gray-300 rounded-lg text-gray-700"
              >
                {{ userLeagueInfo.leagueName }}
              </div>
            </div>

            <!-- Team Selector -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2"
                >Select Club</label
              >
              <select
                v-model="selectedTeam"
                @change="onTeamChange"
                :disabled="
                  !authStore.isAdmin.value && authStore.userTeamId.value
                "
                class="block w-full px-4 py-3 text-base border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-700"
              >
                <option value="">
                  {{
                    authStore.isAdmin.value
                      ? '-- Select a club --'
                      : 'No club assigned'
                  }}
                </option>
                <option
                  v-for="team in filteredTeamsByLeague"
                  :key="team.id"
                  :value="team.id"
                >
                  {{ getTeamDisplayName(team) }}
                </option>
              </select>
            </div>
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

          <!-- Time Range Filter - Only show on "All Matches" tab -->
          <div v-if="selectedViewTab === 'all'">
            <h3 class="text-sm font-medium text-gray-700 mb-2">
              Week Navigation
            </h3>
            <div class="grid grid-cols-3 gap-2">
              <button
                @click="weekOffset--"
                class="px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px] bg-gray-100 text-gray-700 active:bg-gray-300 hover:bg-gray-200"
              >
                ← Previous
              </button>
              <button
                @click="weekOffset = 0"
                :class="[
                  'px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px]',
                  weekOffset === 0
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 active:bg-gray-300 hover:bg-gray-200',
                ]"
              >
                This Week
              </button>
              <button
                @click="weekOffset++"
                class="px-4 py-3 text-sm rounded-lg font-medium transition-colors min-h-[44px] bg-gray-100 text-gray-700 active:bg-gray-300 hover:bg-gray-200"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Display Filtered Matchs -->
      <div v-if="sortedGames.length > 0">
        <div class="mb-4">
          <!-- All Matches: Show week range -->
          <div v-if="selectedViewTab === 'all'">
            <h3 class="text-lg font-semibold mb-2">{{ weekRangeDisplay }}</h3>
          </div>

          <!-- My Club: Show team name and league info -->
          <div v-else>
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
                >{{ selectedTeamLeagueInfo.league }} -
                {{ selectedTeamLeagueInfo.division }} ({{
                  selectedTeamLeagueInfo.ageGroup
                }})</span
              >
              <span class="text-blue-600">• {{ selectedSeasonName }}</span>
            </div>
          </div>
        </div>

        <!-- Season Summary Stats - Only show on My Club tab when a team is selected -->
        <div
          v-if="selectedViewTab === 'myclub' && selectedTeam"
          class="mb-4 space-y-3"
        >
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
              <th
                v-if="selectedViewTab === 'myclub'"
                class="border-b text-right w-12"
              >
                #
              </th>
              <th class="border-b text-center w-32">Date</th>
              <th class="border-b text-left px-2">Team</th>
              <th class="border-b text-center w-24">Score</th>
              <th
                v-if="selectedViewTab === 'myclub'"
                class="border-b text-center w-20"
              >
                Result
              </th>
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
              <td
                v-if="selectedViewTab === 'myclub'"
                class="border-b text-right"
              >
                {{ index + 1 }}
              </td>
              <td class="border-b text-center">{{ match.match_date }}</td>
              <td
                class="border-b text-left px-2"
                v-html="getTeamDisplay(match)"
              ></td>
              <td class="border-b text-center">
                {{ getScoreDisplay(match) }}
              </td>
              <td
                v-if="selectedViewTab === 'myclub'"
                class="border-b text-center"
              >
                <span
                  v-if="
                    match.match_status === 'completed' &&
                    getResult(match) !== '-'
                  "
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
                      match.match_status === 'completed',
                    'bg-blue-100 text-blue-800':
                      match.match_status === 'scheduled',
                    'bg-yellow-100 text-yellow-800':
                      match.match_status === 'postponed',
                    'bg-red-100 text-red-800':
                      match.match_status === 'cancelled',
                    'bg-red-600 text-white font-extrabold text-sm px-4 py-2 animate-pulse shadow-lg whitespace-nowrap':
                      match.match_status === 'live',
                    'bg-gray-100 text-gray-800': !match.match_status,
                  }"
                >
                  {{
                    match.match_status === 'live'
                      ? '🔴 LIVE'
                      : match.match_status || 'scheduled'
                  }}
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
              <div
                class="text-base font-medium text-gray-900 mb-2"
                v-html="getTeamDisplay(match)"
              ></div>
              <div class="flex items-center space-x-3">
                <span class="text-2xl font-bold text-gray-900">
                  {{ getScoreDisplay(match) }}
                </span>
                <span
                  v-if="
                    match.match_status === 'completed' &&
                    getResult(match) !== '-'
                  "
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
                      match.match_status === 'completed',
                    'bg-blue-100 text-blue-800':
                      match.match_status === 'scheduled',
                    'bg-yellow-100 text-yellow-800':
                      match.match_status === 'postponed',
                    'bg-red-100 text-red-800':
                      match.match_status === 'cancelled',
                    'bg-red-600 text-white font-extrabold px-3 py-1 animate-pulse shadow-lg whitespace-nowrap':
                      match.match_status === 'live',
                    'bg-gray-100 text-gray-800': !match.match_status,
                  }"
                >
                  {{
                    match.match_status === 'live'
                      ? '🔴 LIVE'
                      : match.match_status || 'scheduled'
                  }}
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
      :match="editingMatch"
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
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
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
    const leagues = ref([]);
    const selectedViewTab = ref('all'); // Default to "All Matches" tab
    const selectedTeam = ref('');
    const selectedLeagueId = ref(null); // Selected league for My Club tab
    const selectedAgeGroupId = ref(2); // Default to U14
    const selectedSeasonId = ref(3); // Default to 2025-2026
    const selectedMatchTypeId = ref(1); // Default to League matches (id: 1)
    const weekOffset = ref(0); // 0 = current week, -1 = last week, +1 = next week
    const error = ref(null);
    const loading = ref(true);
    const showEditModal = ref(false);
    const editingMatch = ref(null);
    const showFilters = ref(true); // Filters visible by default on mobile
    let liveMatchRefreshInterval = null; // Auto-refresh interval for live matches

    const fetchAgeGroups = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/age-groups`
        );
        ageGroups.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching age groups:', err);
      }
    };

    const fetchSeasons = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/seasons`
        );
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
        matchTypes.value = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/match-types`
        );
      } catch (err) {
        console.error('Error fetching match types:', err);
      }
    };

    const fetchLeagues = async () => {
      try {
        const data = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/leagues`
        );
        leagues.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching leagues:', err);
      }
    };

    const getWeekBoundaries = offset => {
      const now = new Date();
      const dayOfWeek = now.getDay(); // 0 = Sunday, 1 = Monday, etc.

      // Calculate Monday of current week (adjust for Sunday = 0)
      const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
      const currentMonday = new Date(now);
      currentMonday.setDate(now.getDate() - daysFromMonday);
      currentMonday.setHours(0, 0, 0, 0);

      // Apply week offset
      const targetMonday = new Date(currentMonday);
      targetMonday.setDate(currentMonday.getDate() + offset * 7);

      // Calculate Sunday of target week
      const targetSunday = new Date(targetMonday);
      targetSunday.setDate(targetMonday.getDate() + 6);
      targetSunday.setHours(23, 59, 59, 999);

      return {
        start_date: targetMonday.toISOString().split('T')[0],
        end_date: targetSunday.toISOString().split('T')[0],
        start: targetMonday,
        end: targetSunday,
      };
    };

    const fetchTeams = async () => {
      try {
        teams.value = await authStore.apiRequest(
          `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/teams`
        );

        // Auto-select for non-admin users (team managers, fans, players)
        if (authStore.userTeamId && !selectedTeam.value) {
          const playerTeam = teams.value.find(
            team => team.id === authStore.userTeamId.value
          );
          if (playerTeam) {
            // Auto-select the user's team
            selectedTeam.value = String(authStore.userTeamId.value);

            // Auto-select the league for their team
            const teamAgeGroup = playerTeam.age_groups.find(
              ag => ag.id === selectedAgeGroupId.value
            );
            if (teamAgeGroup) {
              const division =
                playerTeam.divisions_by_age_group[
                  String(selectedAgeGroupId.value)
                ];
              if (division && division.league_id) {
                selectedLeagueId.value = division.league_id;
              }
            }

            // Fetch matches for the user's team
            await fetchMatches();
          }
        }
      } catch (err) {
        console.error('Error fetching teams:', err);
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchMatches = async () => {
      if (selectedViewTab.value === 'all') {
        // All Matches view - fetch with date range
        console.log(
          'Fetching matches for All Matches with week offset:',
          weekOffset.value
        );
        const { start_date, end_date } = getWeekBoundaries(weekOffset.value);

        try {
          const url =
            `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/matches?` +
            `start_date=${start_date}&end_date=${end_date}` +
            `&season_id=${selectedSeasonId.value}` +
            `&age_group_id=${selectedAgeGroupId.value}`;
          matches.value = await authStore.apiRequest(url);
          console.log('All Matches received:', matches.value);
        } catch (err) {
          error.value = err.message;
        }
        return; // Exit after fetching All Matches
      }

      // My Club view - fetch team-specific matches
      if (!selectedTeam.value) {
        // No team selected yet in My Club tab
        matches.value = [];
        return;
      }

      try {
        console.log(
          'Fetching matches for team:',
          selectedTeam.value,
          'season:',
          selectedSeasonId.value,
          'age_group:',
          selectedAgeGroupId.value
        );
        const url = `${process.env.VUE_APP_API_URL || 'http://localhost:8000'}/api/matches/team/${selectedTeam.value}?season_id=${selectedSeasonId.value}&age_group_id=${selectedAgeGroupId.value}`;
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
      // All Matches view - show "Away Team @ Home Team" with win/loss/draw icons
      if (selectedViewTab.value === 'all') {
        // Only show icons for completed matches with scores
        if (
          match.match_status === 'completed' &&
          match.home_score !== null &&
          match.home_score !== undefined &&
          match.away_score !== null &&
          match.away_score !== undefined
        ) {
          if (match.away_score > match.home_score) {
            // Away team won - bold winner, green checkmark, red X
            return `<strong>${match.away_team_name}</strong> <span class="text-green-600 font-bold">✓</span> @ ${match.home_team_name} <span class="text-red-600 font-bold">✗</span>`;
          } else if (match.away_score < match.home_score) {
            // Home team won - bold winner, green checkmark, red X
            return `${match.away_team_name} <span class="text-red-600 font-bold">✗</span> @ <strong>${match.home_team_name}</strong> <span class="text-green-600 font-bold">✓</span>`;
          } else {
            // Draw
            return `${match.away_team_name} <span class="text-gray-500">=</span> @ ${match.home_team_name} <span class="text-gray-500">=</span>`;
          }
        }
        // For scheduled/live/postponed matches, no icons
        return `${match.away_team_name} @ ${match.home_team_name}`;
      }

      // My Club view - show opponent with @ or vs
      const selectedTeamId = parseInt(selectedTeam.value);
      if (match.home_team_id === selectedTeamId) {
        return `vs ${match.away_team_name}`;
      } else {
        return `@ ${match.home_team_name}`;
      }
    };

    const getSelectedTeamName = () => {
      const team = teams.value.find(t => t.id === parseInt(selectedTeam.value));
      return team ? team.name : 'Selected Club';
    };

    // Get team display name - now just returns the team name directly
    // Teams are scoped by league in the new clubs architecture
    const getTeamDisplayName = team => {
      return team.name;
    };

    const getScoreDisplay = match => {
      // Show scores for matches that have been completed OR are currently live
      if (match.match_status !== 'completed' && match.match_status !== 'live') {
        return '-'; // Return dash for scheduled/postponed/cancelled matches
      }

      // Check if scores are available
      if (
        match.home_score === null ||
        match.home_score === undefined ||
        match.away_score === null ||
        match.away_score === undefined
      ) {
        return '-'; // Return dash if scores haven't been entered yet
      }

      // All Matches tab: show "Away Score - Home Score" to match "Away @ Home" format
      if (selectedViewTab.value === 'all') {
        return `${match.away_score} - ${match.home_score}`;
      }

      // My Club tab: show "Home Score - Away Score" (traditional format)
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
      // All Matches view - no W/L/D perspective, show dash
      if (selectedViewTab.value === 'all') {
        return '-';
      }

      // ONLY show results for matches that have been completed (not live!)
      if (match.match_status !== 'completed') {
        return '-'; // Return dash for live/scheduled/postponed/cancelled matches
      }

      // Check if scores are available (both scores must be valid numbers)
      if (
        match.home_score === null ||
        match.home_score === undefined ||
        match.away_score === null ||
        match.away_score === undefined
      ) {
        return '-'; // Return dash if scores haven't been entered yet
      }

      // Determine the result for completed matches only
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

    // Filter teams by selected league (for My Club tab)
    const filteredTeamsByLeague = computed(() => {
      // First filter by age group
      let filtered = filteredTeams.value;

      // For admins, filter by selected league
      if (authStore.isAdmin.value && selectedLeagueId.value) {
        filtered = filtered.filter(team => {
          // Ensure type-safe lookup: divisions_by_age_group uses string keys
          const division =
            team.divisions_by_age_group[String(selectedAgeGroupId.value)];

          // Ensure type-safe comparison: convert both to numbers for comparison
          // This handles cases where v-model returns strings from form inputs
          return (
            division &&
            Number(division.league_id) === Number(selectedLeagueId.value)
          );
        });
      }
      // For non-admins, only show their team
      else if (!authStore.isAdmin.value && authStore.userTeamId.value) {
        filtered = filtered.filter(
          team => team.id === authStore.userTeamId.value
        );
      }

      return filtered;
    });

    // Get league info for non-admin user's team
    const userLeagueInfo = computed(() => {
      if (authStore.isAdmin.value || !authStore.userTeamId.value) return null;

      const userTeam = teams.value.find(
        t => t.id === authStore.userTeamId.value
      );
      if (!userTeam) return null;

      const division =
        userTeam.divisions_by_age_group[String(selectedAgeGroupId.value)];
      if (!division) return null;

      return {
        leagueName: division.league_name || 'Unknown League',
        divisionName: division.name,
      };
    });

    // Get league information for selected team
    const selectedTeamLeagueInfo = computed(() => {
      if (!selectedTeam.value) return null;

      const team = teams.value.find(t => t.id === parseInt(selectedTeam.value));
      if (!team) return null;

      const ageGroup = team.age_groups.find(
        ag => ag.id === selectedAgeGroupId.value
      );
      const division =
        team.divisions_by_age_group[String(selectedAgeGroupId.value)];

      if (ageGroup && division) {
        return {
          ageGroup: ageGroup.name,
          division: division.name,
          league: division.league_name || 'Unknown League',
        };
      }

      return null;
    });

    // Get selected season name
    const selectedSeasonName = computed(() => {
      const season = seasons.value.find(s => s.id === selectedSeasonId.value);
      return season ? season.name : '';
    });

    // Get week range display for All Matches tab
    const weekRangeDisplay = computed(() => {
      const boundaries = getWeekBoundaries(weekOffset.value);
      const options = { month: 'short', day: 'numeric' };
      const startStr = boundaries.start.toLocaleDateString('en-US', options);
      const endStr = boundaries.end.toLocaleDateString('en-US', options);
      const year = boundaries.start.getFullYear();
      return `${startStr} - ${endStr}, ${year}`;
    });

    // Sort matches: LIVE matches first, then by date ascending
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

      // Sort: LIVE matches first, then by date ascending
      return filteredGames.sort((a, b) => {
        // LIVE matches always come first
        if (a.match_status === 'live' && b.match_status !== 'live') return -1;
        if (a.match_status !== 'live' && b.match_status === 'live') return 1;

        // For non-LIVE matches (or both LIVE), sort by date
        return new Date(a.match_date) - new Date(b.match_date);
      });
    });

    // Check if there are any live matches
    const hasLiveMatches = computed(() => {
      return matches.value.some(match => match.match_status === 'live');
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

      // Collect all match results first
      const allResults = [];

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

          // Collect all results
          allResults.push(result);
        }
      });

      // Take the last 5 matches and reverse to show most recent first
      stats.lastFive = allResults.slice(-5).reverse();

      // Calculate final stats
      stats.goalDifference = stats.goalsFor - stats.goalsAgainst;
      stats.points = stats.wins * 3 + stats.draws * 1;

      return stats;
    });

    // Watch for changes in age group and season to refresh teams and clear selection
    watch([selectedAgeGroupId, selectedSeasonId], () => {
      // Check if currently selected team is still available in filtered list
      if (selectedTeam.value) {
        const selectedTeamId = parseInt(selectedTeam.value);
        const teamStillAvailable = filteredTeams.value.some(
          team => team.id === selectedTeamId
        );
        if (!teamStillAvailable) {
          selectedTeam.value = ''; // Clear if selected team not in filtered list
          matches.value = []; // Clear matches
        }
        // If team is still available, the age group watcher will refetch matches
      }
    });

    // Watch for tab changes to refetch matches
    watch(selectedViewTab, () => {
      fetchMatches();
    });

    // Watch for team changes to fetch matches (My Club tab)
    watch(selectedTeam, () => {
      if (selectedViewTab.value === 'myclub') {
        fetchMatches();
      }
    });

    // Watch for season changes to refetch matches
    watch(selectedSeasonId, () => {
      fetchMatches();
    });

    // Watch for age group changes to refetch matches
    watch(selectedAgeGroupId, () => {
      fetchMatches();
    });

    // Watch for week offset changes to refetch matches for All Matches view
    watch(weekOffset, () => {
      if (selectedViewTab.value === 'all') {
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
      return authStore.isAdmin.value || authStore.isTeamManager.value;
    });

    const canEditGame = match => {
      // Admins can edit all matches
      if (authStore.isAdmin.value) {
        return true;
      }

      // Team managers can only edit matches involving their team
      // IMPORTANT: userTeamId is a computed property, so we need .value
      if (authStore.isTeamManager.value && authStore.userTeamId.value) {
        return (
          match.home_team_id === authStore.userTeamId.value ||
          match.away_team_id === authStore.userTeamId.value
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

    const onGameUpdated = updatedMatch => {
      console.log('MatchesView - Received updated match:', updatedMatch);

      if (updatedMatch && updatedMatch.id) {
        // Update the match in the local array immediately
        const index = matches.value.findIndex(m => m.id === updatedMatch.id);
        if (index !== -1) {
          console.log(
            'MatchesView - Updating match in local array at index:',
            index
          );
          matches.value[index] = updatedMatch;
          // Force reactivity by creating a new array reference
          matches.value = [...matches.value];
        } else {
          console.log(
            'MatchesView - Match not found in local array, will refetch'
          );
          // Fallback to refetching if match not found
          fetchMatches();
        }
      } else {
        // Fallback: Refresh the matches list if no updated match data provided
        console.log('MatchesView - No updated match data, refetching');
        fetchMatches();
      }
    };

    // Watch for live matches and set up auto-refresh
    watch(hasLiveMatches, newValue => {
      // Clear any existing interval
      if (liveMatchRefreshInterval) {
        clearInterval(liveMatchRefreshInterval);
        liveMatchRefreshInterval = null;
      }

      // If there are live matches, set up auto-refresh every 10 seconds
      if (newValue && selectedTeam.value) {
        console.log(
          'Live match detected - enabling auto-refresh every 10 seconds'
        );
        liveMatchRefreshInterval = setInterval(() => {
          console.log('Auto-refreshing match data for live matches...');
          fetchMatches();
        }, 10000); // Refresh every 10 seconds
      } else {
        console.log('No live matches - auto-refresh disabled');
      }
    });

    onMounted(async () => {
      await Promise.all([
        fetchAgeGroups(),
        fetchSeasons(),
        fetchGameTypes(),
        fetchLeagues(),
        fetchTeams(),
      ]);
      // Fetch matches for the default "All Matches" tab with current week
      await fetchMatches();
    });

    // Clean up interval on component unmount
    onUnmounted(() => {
      if (liveMatchRefreshInterval) {
        clearInterval(liveMatchRefreshInterval);
        liveMatchRefreshInterval = null;
      }
    });

    return {
      teams,
      matches,
      sortedGames,
      ageGroups,
      filteredAgeGroups,
      seasons,
      matchTypes,
      leagues,
      selectedViewTab,
      selectedTeam,
      selectedLeagueId,
      selectedAgeGroupId,
      selectedSeasonId,
      selectedMatchTypeId,
      weekOffset,
      weekRangeDisplay,
      filteredTeams,
      filteredTeamsByLeague,
      userLeagueInfo,
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
      getTeamDisplayName,
      formatSeasonDates,
      getSegmentGridClass,
      canEditGames,
      canEditGame,
      editMatch,
      closeEditModal,
      onGameUpdated,
      showEditModal,
      editingMatch,
      authStore,
    };
  },
};
</script>
