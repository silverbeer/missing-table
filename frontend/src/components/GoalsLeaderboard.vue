<template>
  <div>
    <!-- Beta notice -->
    <div
      v-if="!betaNoticeDismissed"
      class="beta-notice"
      data-testid="leaderboard-beta-notice"
      role="status"
    >
      <div class="beta-notice-body">
        <p>
          <strong>Leaderboard is in beta.</strong>
          Stats shown here are real, but our coverage of the 2025-2026 season is
          still incomplete — some matches and goal data are missing. We're
          targeting a full launch for the 2026-2027 season. Spot something off?
          <SupportEmailLink
            subject="[Leaderboard beta] Feedback"
            :body="supportBody"
          />.
        </p>
      </div>
      <button
        type="button"
        class="beta-notice-dismiss"
        @click="dismissBetaNotice"
        aria-label="Dismiss beta notice"
        data-testid="leaderboard-beta-dismiss"
      >
        ×
      </button>
    </div>

    <!-- Filters Section -->
    <div class="mb-6 space-y-4">
      <!-- Age Group Links -->
      <div data-testid="age-group-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ageGroup in ageGroups"
            :key="ageGroup.id"
            @click="selectedAgeGroupId = ageGroup.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedAgeGroupId === ageGroup.id
                ? 'bg-brand-600 text-white'
                : 'bg-surface-alt text-fg hover:bg-line',
            ]"
            :data-testid="`age-group-${ageGroup.name}`"
          >
            {{ ageGroup.name }}
          </button>
        </div>
      </div>

      <!-- League Selector -->
      <div>
        <h3 class="text-sm font-medium text-fg mb-3">League</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="league in leagues"
            :key="league.id"
            @click="selectedLeagueId = league.id"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedLeagueId === league.id
                ? 'bg-green-600 text-white'
                : 'bg-surface-alt text-fg hover:bg-line',
            ]"
          >
            {{ league.name }}
          </button>
        </div>
      </div>

      <!-- Match Type Filter -->
      <div data-testid="match-type-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Match Type</h3>
        <div class="flex flex-wrap gap-2">
          <button
            @click="selectedMatchTypeId = null"
            :class="[
              'px-4 py-2 text-sm rounded-md font-medium transition-colors',
              selectedMatchTypeId === null
                ? 'bg-purple-600 text-white'
                : 'bg-surface-alt text-fg hover:bg-line',
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
                : 'bg-surface-alt text-fg hover:bg-line',
            ]"
            :data-testid="`match-type-${mt.name}`"
          >
            {{ mt.name }}
          </button>
        </div>
      </div>

      <!-- Tournament Selector (only when Match Type = Tournament) -->
      <div v-if="isTournamentSelected" data-testid="tournament-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Tournament</h3>
        <select
          v-model="selectedTournamentId"
          class="block w-full sm:max-w-md px-3 py-2 bg-card text-fg border border-line rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
          data-testid="tournament-select"
        >
          <option :value="null">All Tournaments</option>
          <option
            v-for="tournament in filteredTournaments"
            :key="tournament.id"
            :value="tournament.id"
          >
            {{ tournament.name }}
          </option>
        </select>
        <p
          v-if="filteredTournaments.length === 0"
          class="mt-2 text-xs text-fg-muted"
        >
          No tournaments for the selected age group.
        </p>
      </div>

      <!-- Season and Division Row -->
      <div
        class="flex flex-col sm:flex-row sm:space-x-6 space-y-4 sm:space-y-0"
      >
        <!-- Season Dropdown -->
        <div class="flex-1">
          <h3 class="text-sm font-medium text-fg mb-3">Season</h3>
          <select
            v-model="selectedSeasonId"
            class="block w-full px-3 py-2 bg-card text-fg border border-line rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
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
          <h3 class="text-sm font-medium text-fg mb-3">Division</h3>
          <select
            v-model="selectedDivisionId"
            class="block w-full px-3 py-2 bg-card text-fg border border-line rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
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
        class="text-center py-8 text-fg-muted"
      >
        No goal scorers found for the selected filters.
      </div>

      <!-- Leaderboard Table -->
      <table
        v-else
        class="min-w-full divide-y divide-line"
        data-testid="leaderboard-table"
      >
        <thead class="bg-surface-alt">
          <tr>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Rank
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Player
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider max-w-[100px] sm:max-w-[140px] md:max-w-none"
            >
              Team
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Goals
            </th>
            <th
              class="hidden sm:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Games
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-medium text-fg-muted uppercase tracking-wider"
            >
              Goals/Game
            </th>
          </tr>
        </thead>
        <tbody
          class="bg-card divide-y divide-line"
          data-testid="leaderboard-body"
        >
          <tr
            v-for="player in leaderboardData"
            :key="player.player_id"
            data-testid="leaderboard-row"
            class="hover:bg-surface-alt"
          >
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-fg-muted"
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
                        : 'bg-transparent text-fg-muted',
                ]"
              >
                {{ player.rank }}
              </span>
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm font-medium text-fg"
            >
              <div class="flex items-center">
                <span class="font-semibold text-base"
                  >#{{ player.jersey_number }}</span
                >
                <span v-if="hasPlayerName(player)" class="ml-2">{{
                  formatPlayerName(player)
                }}</span>
              </div>
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 text-xs sm:text-sm text-fg-muted max-w-[100px] sm:max-w-[140px] md:max-w-none truncate"
            >
              {{ player.team_name || 'Unknown' }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center font-semibold text-fg"
            >
              {{ player.goals }}
            </td>
            <td
              class="hidden sm:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ player.games_played }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
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
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';
import SupportEmailLink from '@/components/SupportEmailLink.vue';

const BETA_NOTICE_DISMISS_KEY = 'leaderboard-beta-notice-dismissed';

export default {
  name: 'GoalsLeaderboard',
  components: { SupportEmailLink },
  setup() {
    const authStore = useAuthStore();
    const leaderboardData = ref([]);
    const ageGroups = ref([]);
    const leagues = ref([]);
    const divisions = ref([]);
    const allDivisions = ref([]);
    const seasons = ref([]);
    const matchTypes = ref([]);
    const tournaments = ref([]);
    const selectedAgeGroupId = ref(null);
    const selectedLeagueId = ref(null);
    const selectedDivisionId = ref(null);
    const selectedSeasonId = ref(null);
    const selectedMatchTypeId = ref(null);
    const selectedTournamentId = ref(null);
    const error = ref(null);
    const loading = ref(true);

    // The match-type id for "Tournament" (seed data id=2, resolved by name).
    const tournamentMatchTypeId = computed(() => {
      const mt = matchTypes.value.find(m => m.name === 'Tournament');
      return mt ? mt.id : null;
    });

    // Tournament dropdown is only shown when the Tournament match type is active.
    const isTournamentSelected = computed(
      () =>
        tournamentMatchTypeId.value !== null &&
        selectedMatchTypeId.value === tournamentMatchTypeId.value
    );

    // Only list tournaments whose age groups include the selected age group.
    const filteredTournaments = computed(() => {
      if (!selectedAgeGroupId.value) {
        return tournaments.value;
      }
      return tournaments.value.filter(t =>
        (t.age_groups || []).some(
          ag => Number(ag.id) === Number(selectedAgeGroupId.value)
        )
      );
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

    const fetchTournaments = async () => {
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments`
        );
        tournaments.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching tournaments:', err);
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

    const hasPlayerName = player => {
      return !!(player.first_name || player.last_name);
    };

    const formatPlayerName = player => {
      if (player.first_name && player.last_name) {
        return `${player.first_name} ${player.last_name}`;
      }
      return player.first_name || player.last_name || '';
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
        if (isTournamentSelected.value && selectedTournamentId.value) {
          url += `&tournament_id=${selectedTournamentId.value}`;
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

    // Clear the tournament selection whenever the Tournament match type is
    // deselected — keeps a stale tournament_id from leaking into other filters.
    watch(selectedMatchTypeId, () => {
      if (!isTournamentSelected.value) {
        selectedTournamentId.value = null;
      }
    });

    // If the age group changes and the chosen tournament no longer matches it,
    // drop the selection so we never query a tournament outside the age group.
    watch(selectedAgeGroupId, () => {
      if (
        selectedTournamentId.value &&
        !filteredTournaments.value.some(
          t => t.id === selectedTournamentId.value
        )
      ) {
        selectedTournamentId.value = null;
      }
    });

    // Watch for changes in filters and refetch data
    watch(
      [
        selectedSeasonId,
        selectedAgeGroupId,
        selectedLeagueId,
        selectedDivisionId,
        selectedMatchTypeId,
        selectedTournamentId,
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
        fetchTournaments(),
      ]);
      await fetchDivisions();
      fetchLeaderboardData();
    });

    const betaNoticeDismissed = ref(
      typeof window !== 'undefined' &&
        window.sessionStorage?.getItem(BETA_NOTICE_DISMISS_KEY) === '1'
    );
    const dismissBetaNotice = () => {
      betaNoticeDismissed.value = true;
      try {
        window.sessionStorage?.setItem(BETA_NOTICE_DISMISS_KEY, '1');
      } catch {
        // sessionStorage can throw in privacy modes — fine to swallow,
        // the ref already updated for this session.
      }
    };
    const supportBody = [
      'Hi support team,',
      '',
      'I have feedback or a report about the Leaderboard beta:',
      '',
    ].join('\n');

    return {
      leaderboardData,
      ageGroups,
      leagues,
      divisions,
      seasons,
      matchTypes,
      tournaments,
      selectedAgeGroupId,
      selectedLeagueId,
      selectedDivisionId,
      selectedSeasonId,
      selectedMatchTypeId,
      selectedTournamentId,
      isTournamentSelected,
      filteredTournaments,
      formatSeasonDates,
      hasPlayerName,
      formatPlayerName,
      error,
      loading,
      betaNoticeDismissed,
      dismissBetaNotice,
      supportBody,
    };
  },
};
</script>

<style scoped>
.beta-notice {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
  padding: 0.875rem 1rem;
  background-color: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  color: #78350f;
}

.beta-notice-body {
  flex: 1;
  font-size: 0.875rem;
  line-height: 1.45;
}

.beta-notice-body p {
  margin: 0;
}

.beta-notice-body strong {
  font-weight: 700;
}

.beta-notice-dismiss {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  line-height: 1;
  color: #92400e;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.beta-notice-dismiss:hover {
  background-color: #fef3c7;
}
</style>
