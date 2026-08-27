<template>
  <div>
    <!-- Filters Section -->
    <div class="mb-6 space-y-4">
      <!-- Age Group Links -->
      <div data-testid="age-group-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ageGroup in ageGroups"
            :key="ageGroup.id"
            @click="selectAgeGroup(ageGroup.id)"
            :class="[
              'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
              selectedAgeGroupId === ageGroup.id
                ? 'bg-brand-500 text-white shadow-sm'
                : 'bg-surface-alt text-fg-muted hover:bg-line',
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
              'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
              selectedLeagueId === league.id
                ? 'bg-brand-500 text-white shadow-sm'
                : 'bg-surface-alt text-fg-muted hover:bg-line',
            ]"
          >
            {{ league.name }}
          </button>
        </div>
      </div>

      <!-- Competition Selector -->
      <!--
        Built from /api/match-types/available (SB-834), not from a
        league-name → competition map. It opens on the division's own
        competition — League for Northeast, Flex for Turnpike — which is the
        `in_division` count doing the work a hardcoded map used to.

        Qualifying appears only when more than one qualifying competition is
        actually present, because with one it would restate the chip beside it.
        A competition with no matches for this selection gets no chip at all.
      -->
      <div v-if="competitionChips.length > 1">
        <h3 class="text-sm font-medium text-fg mb-3">Competition</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="chip in competitionChips"
            :key="chip.key"
            @click="selectedMatchType = chip.value"
            :data-testid="`competition-${chip.key}`"
            :class="[
              'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
              selectedMatchType === chip.value
                ? 'bg-brand-500 text-white shadow-sm'
                : 'bg-surface-alt text-fg-muted hover:bg-line',
            ]"
          >
            {{ chip.label }}
          </button>
        </div>
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
            class="block w-full px-3 py-2 border border-line bg-card text-fg rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
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
            class="block w-full px-3 py-2 border border-line bg-card text-fg rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
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

    <!-- Playoff bracket toggle -->
    <div v-if="bracketExists" class="mb-4 flex justify-end">
      <button
        @click="showBracket = !showBracket"
        class="px-4 py-2 text-sm font-medium rounded-md transition-colors"
        :class="
          showBracket
            ? 'bg-surface-alt text-fg hover:bg-line'
            : 'bg-yellow-500 text-white hover:bg-yellow-600'
        "
      >
        {{ showBracket ? 'Show Standings' : 'Show Playoff Bracket' }}
      </button>
    </div>

    <!-- Playoff Bracket View -->
    <PlayoffBracket
      v-if="
        showBracket &&
        selectedLeagueId &&
        selectedSeasonId &&
        selectedAgeGroupId
      "
      :leagueId="selectedLeagueId"
      :seasonId="selectedSeasonId"
      :ageGroupId="selectedAgeGroupId"
    />

    <!--
      A combined view is a record, not a standing: Flex brackets cut across
      Homegrown divisions, so a team's Qualifying points include results
      against opponents this table does not list. SB-834 returns the count;
      rendering it is what keeps the table honest, per CLAUDE.md — a cross-team
      statistic ships with its coverage or it does not ship.
    -->
    <div
      v-if="!showBracket && outsideTableMatches > 0"
      class="mb-3 px-3 py-2 rounded-md bg-surface-alt text-fg-muted text-sm"
      data-testid="coverage-note"
    >
      {{ coverageLabel }}
    </div>

    <div v-if="!showBracket" class="overflow-x-auto">
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
        class="min-w-full divide-y divide-line"
        data-testid="standings-table"
      >
        <thead class="bg-brand-500">
          <tr>
            <th
              class="px-1 sm:px-2 md:px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Rank"
            >
              #
            </th>
            <th
              class="hidden md:table-cell px-1 sm:px-2 md:px-3 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Position change since last week"
            >
              +/-
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider max-w-[100px] sm:max-w-[140px] md:max-w-none"
            >
              Team
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Games Played"
              :aria-sort="ariaSort('played')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-played"
                @click="toggleSort('played')"
              >
                GP<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('played')
                }}</span>
              </button>
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Wins"
              :aria-sort="ariaSort('wins')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-wins"
                @click="toggleSort('wins')"
              >
                W<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('wins')
                }}</span>
              </button>
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Draws"
              :aria-sort="ariaSort('draws')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-draws"
                @click="toggleSort('draws')"
              >
                D<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('draws')
                }}</span>
              </button>
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Losses"
              :aria-sort="ariaSort('losses')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-losses"
                @click="toggleSort('losses')"
              >
                L<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('losses')
                }}</span>
              </button>
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Goals For"
              :aria-sort="ariaSort('goals_for')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-goals-for"
                @click="toggleSort('goals_for')"
              >
                GF<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('goals_for')
                }}</span>
              </button>
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Goals Against"
              :aria-sort="ariaSort('goals_against')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-goals-against"
                @click="toggleSort('goals_against')"
              >
                GA<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('goals_against')
                }}</span>
              </button>
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Goal Difference"
              :aria-sort="ariaSort('goal_difference')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-goal-difference"
                @click="toggleSort('goal_difference')"
              >
                GD<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('goal_difference')
                }}</span>
              </button>
            </th>
            <th
              class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-brand-200 uppercase tracking-wider"
              title="Points"
              :aria-sort="ariaSort('points')"
            >
              <button
                type="button"
                class="sort-header"
                data-testid="sort-points"
                @click="toggleSort('points')"
              >
                Pts<span class="sort-caret" aria-hidden="true">{{
                  sortCaret('points')
                }}</span>
              </button>
            </th>
            <th
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
              title="Last 5 results"
            >
              Form
            </th>
            <th
              v-if="hasQopData"
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
            >
              <span title="Quality of Play rank — updated weekly by MLS Next"
                >QoP</span
              >
            </th>
          </tr>
        </thead>
        <tbody
          class="bg-card divide-y divide-line"
          data-testid="standings-body"
        >
          <tr
            v-for="team in sortedTableData"
            :key="team.team"
            class="hover:bg-surface-alt transition-colors"
            data-testid="standings-row"
          >
            <!-- League position, not row number: sorting by GF must not renumber
                 the standings. -->
            <td
              class="px-1 sm:px-2 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-fg-muted"
            >
              {{ team.standingsRank }}
            </td>
            <td
              class="hidden md:table-cell px-1 sm:px-2 md:px-3 py-3 md:py-4 whitespace-nowrap text-xs text-center"
            >
              <span
                v-if="team.position_change > 0"
                class="text-green-600 font-medium"
                :title="`Up ${team.position_change}`"
              >
                ▲ {{ team.position_change }}
              </span>
              <span
                v-else-if="team.position_change < 0"
                class="text-red-600 font-medium"
                :title="`Down ${Math.abs(team.position_change)}`"
              >
                ▼ {{ Math.abs(team.position_change) }}
              </span>
              <span v-else class="text-fg-muted">—</span>
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 text-xs sm:text-sm font-medium text-fg max-w-[100px] sm:max-w-[140px] md:max-w-none md:whitespace-nowrap"
            >
              <div class="flex items-center gap-1.5">
                <ClubLogo
                  :logo-url="team.logo_url"
                  :name="team.team"
                  size="xs"
                />
                <button
                  v-if="team.team_id"
                  type="button"
                  @click="handleTeamClick(team)"
                  data-testid="standings-team-link"
                  class="text-left text-brand-600 hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200 hover:underline focus:outline-none focus:underline"
                >
                  {{ getTeamDisplayName(team.team) }}
                </button>
                <span v-else>{{ getTeamDisplayName(team.team) }}</span>
              </div>
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.played }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.wins }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.draws }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.losses }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.goals_for }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.goals_against }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center text-fg-muted"
            >
              {{ team.goal_difference }}
            </td>
            <td
              class="px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center font-bold text-accent-600 dark:text-accent-300"
            >
              {{ team.points }}
            </td>
            <td
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-center"
            >
              <div class="flex items-center justify-center gap-1">
                <span
                  v-for="(result, rIdx) in team.form || []"
                  :key="rIdx"
                  class="inline-block w-5 h-5 rounded-full text-[10px] font-bold leading-5 text-white text-center"
                  :class="{
                    'bg-green-500': result === 'W',
                    'bg-red-500': result === 'L',
                    'bg-gray-400': result === 'D',
                  }"
                  :title="
                    result === 'W' ? 'Win' : result === 'L' ? 'Loss' : 'Draw'
                  "
                >
                  {{ result }}
                </span>
              </div>
            </td>
            <td
              v-if="hasQopData"
              class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 md:py-4 whitespace-nowrap text-sm text-center"
            >
              <template v-if="team.qop_rank != null">
                <span class="font-medium">#{{ team.qop_rank }}</span>
                <span
                  v-if="team.qop_rank_change > 0"
                  class="ml-1 text-xs text-green-600"
                  >▲{{ team.qop_rank_change }}</span
                >
                <span
                  v-else-if="team.qop_rank_change < 0"
                  class="ml-1 text-xs text-red-600"
                  >▼{{ Math.abs(team.qop_rank_change) }}</span
                >
                <span v-else class="ml-1 text-xs text-fg-muted">—</span>
              </template>
              <span v-else class="text-fg-muted">—</span>
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
import PlayoffBracket from './PlayoffBracket.vue';
import ClubLogo from './shared/ClubLogo.vue';

export default {
  name: 'LeagueTable',
  components: { PlayoffBracket, ClubLogo },
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
  emits: ['navigate-to-team'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const tableData = ref([]);

    // Column sorting (SB-427). A null sortKey means league position — the
    // default, so the standings still read as standings until asked otherwise.
    const sortKey = ref(null);
    const sortDir = ref('desc');

    // Stamp league position before any re-ordering, so the rank column keeps
    // showing where a team actually sits in the table.
    const rankedTableData = computed(() =>
      tableData.value.map((team, index) => ({
        ...team,
        standingsRank: index + 1,
      }))
    );

    const sortedTableData = computed(() => {
      if (!sortKey.value) return rankedTableData.value;
      const key = sortKey.value;
      const direction = sortDir.value === 'asc' ? 1 : -1;
      return [...rankedTableData.value].sort((a, b) => {
        const av = Number(a[key] ?? 0);
        const bv = Number(b[key] ?? 0);
        // Ties fall back to league position, so equal rows never shuffle.
        return av === bv
          ? a.standingsRank - b.standingsRank
          : (av - bv) * direction;
      });
    });

    // desc (answers "who has the most") -> asc -> back to league position.
    const toggleSort = key => {
      if (sortKey.value !== key) {
        sortKey.value = key;
        sortDir.value = 'desc';
      } else if (sortDir.value === 'desc') {
        sortDir.value = 'asc';
      } else {
        sortKey.value = null;
        sortDir.value = 'desc';
      }
    };

    const ariaSort = key => {
      if (sortKey.value !== key) return 'none';
      return sortDir.value === 'asc' ? 'ascending' : 'descending';
    };

    const sortCaret = key => {
      if (sortKey.value !== key) return '';
      return sortDir.value === 'asc' ? ' ▲' : ' ▼';
    };
    const teams = ref([]); // Store all teams for name→id mapping
    const ageGroups = ref([]);
    const leagues = ref([]);
    const divisions = ref([]);
    const allDivisions = ref([]); // Store all divisions for filtering
    const seasons = ref([]);
    const selectedAgeGroupId = ref(2); // Default to U14 (anonymous fallback)
    // True once the viewer picks an age group themselves, so a late-arriving
    // profile can't yank the table back to their own age group (SB-599).
    const ageGroupTouched = ref(false);
    const selectAgeGroup = id => {
      ageGroupTouched.value = true;
      selectedAgeGroupId.value = id;
    };
    const selectedLeagueId = ref(null); // Default to first league
    const selectedDivisionId = ref(1); // Default to Northeast
    const selectedSeasonId = ref(2); // Default to 2024-2025
    const error = ref(null);
    const loading = ref(true);

    // Competition state (SB-835). `selectedMatchType` is a match_type name or
    // the string 'qualifying' — never a hardcoded id, and never derived from
    // the league's name.
    const competitions = ref([]);
    const selectedMatchType = ref('League');

    // Coverage returned with the table: how much of it was played against
    // teams outside it.
    const coverage = ref(null);

    // QoP state
    const hasQopData = ref(false);
    const qopWeekOf = ref(null);

    // Playoff bracket state
    const bracketExists = ref(false);
    const showBracket = ref(false);

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

        // Prefer the viewer's own age group; U14 is the anonymous fallback.
        const personal = authStore.userAgeGroupId?.value;
        const u14 = data.find(ag => ag.name === 'U14');
        if (personal && data.some(ag => ag.id === personal)) {
          selectedAgeGroupId.value = personal;
        } else if (u14) {
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

    // Only leagues worth offering for the season being viewed: active, or with
    // matches in it (SB-851). Kick Futsal is inactive and its 24 matches are
    // all 2025-2026, so it used to appear on every season and yield an empty
    // table on all but one of them.
    const fetchLeagues = async () => {
      try {
        const params = new URLSearchParams({
          season_id: selectedSeasonId.value,
        });
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/leagues/available?${params}`
        );
        leagues.value = data.sort((a, b) => a.name.localeCompare(b.name));
      } catch (err) {
        console.error('Error fetching leagues:', err);
        return;
      }

      // Keep the current league when the new season still offers it; a season
      // change should not silently move the viewer somewhere else.
      if (leagues.value.some(l => l.id === selectedLeagueId.value)) return;

      const homegrown = leagues.value.find(l => l.name === 'Homegrown');
      selectedLeagueId.value = homegrown?.id ?? leagues.value[0]?.id ?? null;
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

        // Default to the admin-set current season (falls back to newest).
        const current = data.find(s => s.is_current) || seasons.value[0];
        if (current) {
          selectedSeasonId.value = current.id;
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

    const handleTeamClick = row => {
      if (!row.team_id) return;
      emit('navigate-to-team', {
        teamId: row.team_id,
        clubId: row.club_id,
        ageGroupId: selectedAgeGroupId.value,
        leagueId: selectedLeagueId.value,
        divisionId: selectedDivisionId.value,
        seasonId: selectedSeasonId.value,
      });
    };

    // One chip per competition actually played by this selection, in the order
    // the API gives (display_order), plus a synthetic Qualifying.
    const competitionChips = computed(() => {
      const present = (competitions.value || []).map(c => ({
        key: String(c.id),
        label: c.name,
        value: c.name,
        qualifies: Boolean(c.counts_for_qualification),
      }));

      const chips = [...present];

      // Qualifying only says something the individual chips do not when it
      // combines more than one of them.
      const qualifying = present.filter(c => c.qualifies);
      if (qualifying.length > 1) {
        const lastIndex = chips.map(c => c.qualifies).lastIndexOf(true);
        chips.splice(lastIndex + 1, 0, {
          key: 'qualifying',
          label: 'Qualifying',
          value: 'qualifying',
          qualifies: true,
        });
      }

      return chips;
    });

    // The competition a division opens on: the one its own matches are filed
    // under. Northeast opens on League, Turnpike on Flex. `in_division` is how
    // the API says so, which is why there is no league-name lookup here.
    const defaultMatchType = () => {
      const own = (competitions.value || []).find(c => c.in_division > 0);
      return own?.name || competitions.value?.[0]?.name || 'League';
    };

    const fetchCompetitions = async () => {
      try {
        const params = new URLSearchParams({
          season_id: selectedSeasonId.value,
          age_group_id: selectedAgeGroupId.value,
          division_id: selectedDivisionId.value,
        });
        competitions.value = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/match-types/available?${params}`
        );
      } catch (err) {
        console.error('Error fetching competitions:', err);
        competitions.value = [];
      }

      // Keep the selection only if this division still plays it. Otherwise
      // fall back to the division's own competition rather than leaving a
      // filter set to something with no matches.
      const values = new Set(competitionChips.value.map(c => c.value));
      if (!values.has(selectedMatchType.value)) {
        selectedMatchType.value = defaultMatchType();
      }
    };

    const outsideTableMatches = computed(
      () => coverage.value?.matches_vs_outside_table || 0
    );

    const coverageLabel = computed(() => {
      const c = coverage.value;
      if (!c) return '';
      const names = (c.competitions || []).join(' + ') || 'all competitions';
      const matches = c.matches_vs_outside_table;
      const teams = c.teams_outside_table;
      return (
        `${names} combined — includes ${matches} ` +
        `${matches === 1 ? 'match' : 'matches'} against ` +
        `${teams} ${teams === 1 ? 'team' : 'teams'} outside this table. ` +
        'A record, not a standing.'
      );
    });

    const fetchTableData = async () => {
      loading.value = true;
      console.log('Fetching table data...', {
        seasonId: selectedSeasonId.value,
        ageGroupId: selectedAgeGroupId.value,
        divisionId: selectedDivisionId.value,
      });
      try {
        // match_type is sent explicitly. Omitting it let the API default to
        // League, so picking a Flex bracket asked for League matches in a
        // division that has none and rendered an empty table (SB-835).
        const url =
          `${getApiBaseUrl()}/api/table?season_id=${selectedSeasonId.value}` +
          `&age_group_id=${selectedAgeGroupId.value}` +
          `&division_id=${selectedDivisionId.value}` +
          `&match_type=${encodeURIComponent(selectedMatchType.value)}`;

        const data = await authStore.apiRequest(url);
        console.log('Table data received:', data);

        // Unwrap new response shape: { has_qop_data, qop_week_of, standings: [...] }
        if (data && typeof data === 'object' && 'standings' in data) {
          tableData.value = data.standings;
          hasQopData.value = data.has_qop_data ?? false;
          qopWeekOf.value = data.qop_week_of ?? null;
          coverage.value = data.coverage ?? null;
        } else {
          // Fallback for bare-array responses (backwards compat)
          tableData.value = data;
          hasQopData.value = false;
          qopWeekOf.value = null;
          coverage.value = null;
        }
        console.log('Table data set:', tableData.value);
      } catch (err) {
        console.error('Error fetching table data:', err);
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const checkBracketExists = async () => {
      bracketExists.value = false;
      showBracket.value = false;
      if (
        !selectedLeagueId.value ||
        !selectedSeasonId.value ||
        !selectedAgeGroupId.value
      )
        return;
      try {
        const params = new URLSearchParams({
          league_id: selectedLeagueId.value,
          season_id: selectedSeasonId.value,
          age_group_id: selectedAgeGroupId.value,
        });
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/playoffs/bracket?${params}`,
          { method: 'GET' }
        );
        bracketExists.value = Array.isArray(data) && data.length > 0;
      } catch {
        // Bracket check is non-critical — ignore errors
      }
    };

    // Declared before the table watchers so a season change re-reads the
    // leagues, and any resulting league change cascades before the table is
    // asked for.
    watch(selectedSeasonId, async () => {
      await fetchLeagues();
    });

    // Watch for league changes to filter divisions and check bracket
    watch(selectedLeagueId, () => {
      filterDivisionsByLeague();
      checkBracketExists();
    });

    // Which competitions exist depends on the season, age group and division,
    // so they are re-read before the table is. fetchCompetitions reconciles
    // selectedMatchType, and the watch below picks up any change it makes.
    watch(
      [selectedSeasonId, selectedAgeGroupId, selectedDivisionId],
      async () => {
        await fetchCompetitions();
        fetchTableData();
      }
    );

    watch(selectedMatchType, () => {
      fetchTableData();
    });

    // Re-check bracket when season or age group changes
    watch([selectedSeasonId, selectedAgeGroupId], () => {
      checkBracketExists();
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

    // On a cold load the profile can resolve after this component mounts, so the
    // personalization in fetchAgeGroups() has nothing to read. Re-apply it when the
    // profile lands — but never over a choice the viewer already made (SB-599).
    watch(
      () => authStore.userAgeGroupId?.value,
      personal => {
        if (!personal || ageGroupTouched.value) return;
        if (props.filterKey > 0 && props.initialAgeGroupId) return;
        if (!ageGroups.value.some(ag => ag.id === personal)) return;
        selectedAgeGroupId.value = personal;

        const personalLeagueId = authStore.userLeagueId?.value;
        const personalDivisionId = authStore.userDivisionId?.value;
        if (personalLeagueId && personalDivisionId) {
          selectedLeagueId.value = personalLeagueId;
          filterDivisionsByLeague();
          selectedDivisionId.value = personalDivisionId;
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

      // Seasons first: which leagues are worth offering depends on the season,
      // so fetching them together would race.
      await Promise.all([fetchAgeGroups(), fetchSeasons(), fetchTeams()]);
      await fetchLeagues();

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
      } else if (
        !authStore.isAdmin.value &&
        authStore.userCurrentTeamId?.value
      ) {
        // For non-admins without explicit filters, auto-select based on their team.
        // The league/division on their current-season roster row is authoritative
        // (it is age-specific), so prefer it over the team-level lookup (SB-599).
        const personalLeagueId = authStore.userLeagueId?.value;
        const personalDivisionId = authStore.userDivisionId?.value;
        if (personalLeagueId && personalDivisionId) {
          selectedLeagueId.value = personalLeagueId;
          selectedDivisionId.value = personalDivisionId;
          filterDivisionsByLeague();
        } else {
          try {
            // Fetch the user's team to get its league and division
            const teams = await authStore.apiRequest(
              `${getApiBaseUrl()}/api/teams`
            );
            const userTeam = teams.find(
              t => t.id === authStore.userCurrentTeamId?.value
            );

            if (userTeam) {
              // Get division for selected age group
              // Ensure type-safe lookup: divisions_by_age_group uses string keys
              const division =
                userTeam.divisions_by_age_group[
                  String(selectedAgeGroupId.value)
                ];
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
      }

      // Before the first table request, so it asks for a competition this
      // division actually plays rather than defaulting to League.
      await fetchCompetitions();

      fetchTableData();
      checkBracketExists();
    });

    return {
      tableData,
      sortedTableData,
      sortKey,
      sortDir,
      toggleSort,
      ariaSort,
      sortCaret,
      hasQopData,
      qopWeekOf,
      competitions,
      competitionChips,
      selectedMatchType,
      coverage,
      outsideTableMatches,
      coverageLabel,
      ageGroups,
      leagues,
      divisions,
      seasons,
      selectedAgeGroupId,
      selectAgeGroup,
      selectedLeagueId,
      selectedLeagueName,
      selectedDivisionId,
      selectedSeasonId,
      formatSeasonDates,
      getTeamDisplayName,
      handleTeamClick,
      error,
      loading,
      bracketExists,
      showBracket,
      authStore,
    };
  },
};
</script>

<style scoped>
/* Header buttons inherit the th's type styling — the header must still look
   like a header, not a form control. */
.sort-header {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  font: inherit;
  color: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
}

.sort-header:hover {
  color: #fff;
}

.sort-header:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
  border-radius: 2px;
}

/* Reserve the caret's width so activating a sort doesn't nudge the columns. */
.sort-caret {
  display: inline-block;
  min-width: 0.75em;
}
</style>
