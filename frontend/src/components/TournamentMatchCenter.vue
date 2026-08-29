<template>
  <!-- Match detail modal: overlays the tournament page when a row or bracket
       cell is clicked. ModalOverlay owns the close affordances -- pinned
       button, Escape, backdrop -- plus scroll lock and focus handling. -->
  <ModalOverlay
    v-if="selectedMatchId"
    label="Match details"
    close-label="Close match details"
    @close="handleBackFromMatchDetail"
  >
    <MatchDetailView
      :matchId="selectedMatchId"
      back-label="Back to tournament"
      @back="handleBackFromMatchDetail"
    />
  </ModalOverlay>

  <div
    :class="
      viewMode === 'bracket' || viewMode === 'standings'
        ? 'max-w-7xl mx-auto'
        : 'max-w-4xl mx-auto'
    "
  >
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
      ></div>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4"
    >
      <p class="text-red-800">{{ error }}</p>
    </div>

    <template v-else>
      <!-- Season selector: always visible so the user can switch seasons even
           when the selected season has no tournaments. -->
      <div v-if="seasons.length > 0" class="mb-6 max-w-xs">
        <label
          for="tournament-season"
          class="block text-sm font-medium text-fg mb-1"
          >Season</label
        >
        <select
          id="tournament-season"
          v-model="selectedSeasonId"
          data-testid="tournament-season-select"
          class="block w-full px-3 py-2 border border-line bg-card text-fg rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
        >
          <option v-for="season in seasons" :key="season.id" :value="season.id">
            {{ season.name }} ({{ formatSeasonDates(season) }})
          </option>
        </select>
      </div>

      <!-- No tournaments in the selected season -->
      <div
        v-if="tournaments.length === 0"
        class="text-center py-16 text-fg-muted"
      >
        <div class="text-5xl mb-4">🏆</div>
        <p class="text-lg font-medium text-fg">No tournaments this season</p>
        <p class="text-sm mt-1">
          Try another season, or check back soon for upcoming events.
        </p>
      </div>

      <template v-else>
        <!-- Tournament selector (only shown when multiple active) -->
        <div v-if="tournaments.length > 1" class="mb-6 flex flex-wrap gap-2">
          <button
            v-for="t in tournaments"
            :key="t.id"
            @click="selectTournament(t.id)"
            :class="[
              'px-4 py-2 rounded-full text-sm font-medium transition-colors',
              selectedId === t.id
                ? 'bg-brand-600 text-white'
                : 'bg-card border border-line text-fg hover:border-brand-400',
            ]"
          >
            {{ t.name }}
          </button>
        </div>

        <!-- Tournament detail -->
        <div v-if="selected">
          <!-- Hero card: says where the tournament is in its own life before
               it says what is in it. -->
          <TournamentHeroCard
            :tournament="selected"
            :matches="selected.matches || []"
            :my-club-id="myClubId"
            :my-team-id="myTeamId"
            :stage-label="stageLabel"
            @select-match="viewMatch"
          >
            <template #actions>
              <!-- View toggle: List always shown; Bracket / Standings shown
                   based on match round shape -->
              <div
                v-if="hasBracketRounds || hasStandingsRounds"
                class="inline-flex rounded-md border border-line bg-card p-0.5 shrink-0"
              >
                <button
                  type="button"
                  @click="viewMode = 'list'"
                  :class="[
                    'px-3 py-1 text-xs font-medium rounded transition-colors',
                    viewMode === 'list'
                      ? 'bg-brand-600 text-white'
                      : 'text-fg-muted hover:text-fg',
                  ]"
                >
                  List
                </button>
                <button
                  v-if="hasBracketRounds"
                  type="button"
                  @click="viewMode = 'bracket'"
                  :class="[
                    'px-3 py-1 text-xs font-medium rounded transition-colors',
                    viewMode === 'bracket'
                      ? 'bg-brand-600 text-white'
                      : 'text-fg-muted hover:text-fg',
                  ]"
                >
                  Bracket
                </button>
                <button
                  v-if="hasStandingsRounds"
                  type="button"
                  @click="viewMode = 'standings'"
                  :class="[
                    'px-3 py-1 text-xs font-medium rounded transition-colors',
                    viewMode === 'standings'
                      ? 'bg-brand-600 text-white'
                      : 'text-fg-muted hover:text-fg',
                  ]"
                >
                  Standings
                </button>
              </div>
            </template>
          </TournamentHeroCard>
          <!-- Match loading -->
          <div v-if="matchesLoading" class="flex justify-center py-8">
            <div
              class="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600"
            ></div>
          </div>

          <template v-else-if="selected.matches && viewMode === 'list'">
            <!-- Age group filter -->
            <div
              v-if="availableAgeGroups.length > 1"
              class="mb-4 flex flex-wrap gap-2"
            >
              <button
                @click="ageGroupFilter = null"
                :class="[
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  ageGroupFilter === null
                    ? 'bg-brand-600 text-white'
                    : 'bg-card border border-line text-fg hover:border-brand-400',
                ]"
              >
                All Ages
              </button>
              <button
                v-for="ag in availableAgeGroups"
                :key="ag.id"
                @click="ageGroupFilter = ag.id"
                :class="[
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  ageGroupFilter === ag.id
                    ? 'bg-brand-600 text-white'
                    : 'bg-card border border-line text-fg hover:border-brand-400',
                ]"
              >
                {{ ag.name }}
              </button>
            </div>

            <!-- Team filter: only earns its row once the list is long enough
                 to need filtering. The match count lives in the hero card. -->
            <div
              v-if="showTeamFilter"
              class="mb-4 flex flex-wrap items-center gap-3"
            >
              <input
                v-model="teamFilter"
                type="text"
                placeholder="Filter by team…"
                class="px-3 py-2 bg-card border border-line rounded-md text-sm text-fg focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-48"
              />
              <span class="text-sm text-fg-muted"
                >{{ filteredMatches.length }} match{{
                  filteredMatches.length !== 1 ? 'es' : ''
                }}</span
              >
              <button
                v-if="teamFilter || ageGroupFilter"
                @click="
                  teamFilter = '';
                  ageGroupFilter = null;
                "
                class="text-sm text-brand-600 dark:text-brand-300 hover:text-brand-800 dark:hover:text-brand-200"
              >
                clear all
              </button>
            </div>
            <!-- Age filter is on but the team input is hidden: still offer a
                 way back to the unfiltered list. -->
            <div v-else-if="ageGroupFilter" class="mb-4">
              <button
                @click="ageGroupFilter = null"
                class="text-sm text-brand-600 dark:text-brand-300 hover:text-brand-800 dark:hover:text-brand-200"
              >
                clear filter
              </button>
            </div>

            <!-- No matches -->
            <div
              v-if="selected.matches.length === 0"
              class="text-center py-10 text-fg-muted"
            >
              No matches entered yet.
            </div>
            <!-- Matches exist, but the current filter hides all of them. This
                 is a filter result, not an empty tournament — say so. -->
            <div
              v-else-if="filteredMatches.length === 0"
              class="text-center py-10 text-fg-muted"
            >
              No matches match this filter.
            </div>

            <!-- Group stage / Knockout / Matches, each grouped by day. -->
            <div
              v-for="section in listSections"
              :key="section.key"
              class="mb-6"
              data-testid="tournament-section"
            >
              <h3
                class="text-xs font-semibold text-fg-muted uppercase tracking-wider mb-2"
              >
                {{ section.title }}
              </h3>

              <div
                v-for="day in section.days"
                :key="`${section.key}-${day.date ?? 'undated'}`"
                class="mb-3 last:mb-0"
              >
                <!-- Day band: carries the date once for the whole day, and
                     says "Today" / "Tomorrow" when that is more useful than
                     a weekday. -->
                <div
                  class="flex items-center gap-3 px-0.5 pb-1.5"
                  data-testid="tournament-day-band"
                >
                  <span
                    class="text-sm font-bold text-fg uppercase tracking-wide"
                  >
                    {{ formatDayBand(day.date) }}
                    <span
                      v-if="relativeDay(day.date)"
                      class="text-accent-600 dark:text-accent-400"
                      >· {{ relativeDay(day.date) }}</span
                    >
                  </span>
                  <span class="flex-1 h-px bg-line"></span>
                  <span class="text-xs text-fg-muted tabular-nums shrink-0">
                    {{ day.matches.length }}
                    {{ day.matches.length === 1 ? 'match' : 'matches' }}
                  </span>
                </div>

                <div class="space-y-1.5">
                  <TournamentMatchRow
                    v-for="match in day.matches"
                    :key="match.id"
                    :match="match"
                    :show-age-chip="showAgeChip"
                    :show-round-chip="section.showRoundChip"
                    :show-group-chip="section.showGroupChip"
                    :my-club-id="myClubId"
                    :my-team-id="myTeamId"
                    :can-edit="canEditMatchRow(match)"
                    :saving="savingMatchId === match.id"
                    :save-error="saveErrorMatchId === match.id ? saveError : ''"
                    @select="viewMatch"
                    @save="saveScore"
                  />
                </div>
              </div>
            </div>
          </template>
          <!-- ── Bracket view ── -->
          <template v-else-if="selected.matches && viewMode === 'bracket'">
            <!-- Selectors: age group + bracket group -->
            <div
              class="mb-5 flex flex-col sm:flex-row sm:items-center sm:flex-wrap gap-3"
            >
              <div
                v-if="bracketAgeGroups.length > 0"
                class="flex flex-wrap items-center gap-2"
              >
                <span
                  class="text-xs font-semibold text-fg-muted uppercase tracking-wider mr-1"
                  >Age</span
                >
                <button
                  v-for="ag in bracketAgeGroups"
                  :key="`bag-${ag.id}`"
                  @click="bracketAgeGroupId = ag.id"
                  :class="[
                    'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                    bracketAgeGroupId === ag.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-card border border-line text-fg hover:border-indigo-400',
                  ]"
                >
                  {{ ag.name }}
                </button>
              </div>
              <div
                v-if="bracketGroups.length > 1"
                class="flex flex-wrap items-center gap-2"
              >
                <span
                  class="text-xs font-semibold text-fg-muted uppercase tracking-wider mr-1"
                  >Bracket</span
                >
                <button
                  v-for="g in bracketGroups"
                  :key="`bg-${g}`"
                  @click="bracketGroup = g"
                  :class="[
                    'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                    bracketGroup === g
                      ? 'bg-brand-600 text-white'
                      : 'bg-card border border-line text-fg hover:border-brand-400',
                  ]"
                >
                  {{ g }}
                </button>
              </div>

              <!-- Follow this bracket: push at fulltime for every match in
                 (tournament + group + age group). Two-state toggle. -->
              <button
                v-if="canFollowBracket"
                type="button"
                @click="toggleBracketFollow"
                data-testid="bracket-follow-toggle"
                :class="[
                  'sm:ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  isBracketFollowed
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-card border border-line text-fg hover:border-brand-400',
                ]"
              >
                <span v-if="isBracketFollowed">✓ Following — Unfollow</span>
                <span v-else>🔔 Follow this bracket</span>
              </button>
              <span
                v-else-if="bracketNeedsPush"
                class="sm:ml-auto text-xs text-fg-muted"
                data-testid="bracket-follow-push-hint"
              >
                🔔 Enable notifications in your profile to follow this bracket.
              </span>
            </div>

            <TournamentBracket
              :matches="bracketMatches"
              @match-click="viewMatch"
            />
          </template>

          <!-- ── Standings view ── -->
          <template v-else-if="selected.matches && viewMode === 'standings'">
            <!-- Selectors: age group + tournament group, reused pattern from Bracket -->
            <div
              class="mb-5 flex flex-col sm:flex-row sm:items-center sm:flex-wrap gap-3"
            >
              <div
                v-if="standingsAgeGroups.length > 1"
                class="flex flex-wrap items-center gap-2"
              >
                <span
                  class="text-xs font-semibold text-fg-muted uppercase tracking-wider mr-1"
                  >Age</span
                >
                <button
                  v-for="ag in standingsAgeGroups"
                  :key="`sag-${ag.id}`"
                  @click="standingsAgeGroupId = ag.id"
                  :class="[
                    'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                    standingsAgeGroupId === ag.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-card border border-line text-fg hover:border-indigo-400',
                  ]"
                >
                  {{ ag.name }}
                </button>
              </div>
              <div
                v-if="standingsGroups.length > 1"
                class="flex flex-wrap items-center gap-2"
              >
                <span
                  class="text-xs font-semibold text-fg-muted uppercase tracking-wider mr-1"
                  >Bracket</span
                >
                <button
                  v-for="g in standingsGroups"
                  :key="`sg-${g}`"
                  @click="standingsGroup = g"
                  :class="[
                    'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                    standingsGroup === g
                      ? 'bg-brand-600 text-white'
                      : 'bg-card border border-line text-fg hover:border-brand-400',
                  ]"
                >
                  {{ g }}
                </button>
              </div>

              <!-- Follow this bracket: group-stage pools (e.g. NAC 'Bracket A')
                 render here. Push at fulltime for every match in the selected
                 tournament + group + age. Two-state toggle. -->
              <button
                v-if="canFollowStandingsBracket"
                type="button"
                @click="toggleStandingsBracketFollow"
                data-testid="standings-bracket-follow-toggle"
                :class="[
                  'sm:ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  isStandingsBracketFollowed
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-card border border-line text-fg hover:border-brand-400',
                ]"
              >
                <span v-if="isStandingsBracketFollowed"
                  >✓ Following — Unfollow</span
                >
                <span v-else>🔔 Follow this bracket</span>
              </button>
              <span
                v-else-if="standingsNeedsPush"
                class="sm:ml-auto text-xs text-fg-muted"
                data-testid="standings-bracket-follow-push-hint"
              >
                🔔 Enable notifications in your profile to follow this bracket.
              </span>
            </div>

            <TournamentStandings :matches="standingsMatches" />
          </template>
        </div>
      </template>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted, unref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';
import TournamentBracket from './TournamentBracket.vue';
import TournamentStandings from './TournamentStandings.vue';
import MatchDetailView from './MatchDetailView.vue';
import ModalOverlay from './ui/ModalOverlay.vue';
import TournamentHeroCard from './TournamentHeroCard.vue';
import TournamentMatchRow from './TournamentMatchRow.vue';
import { useBracketFollows } from '../composables/useBracketFollows';
import { usePushNotifications } from '../composables/usePushNotifications';
import {
  compareByStatus,
  groupMatchesByDay,
  relativeDayLabel,
} from '../utils/tournamentStatus';
import { canEditMatch } from '../utils/matchPermissions';

// Past this many matches the list is long enough that a team filter earns its
// row. Below it the input is larger than the thing it filters.
const TEAM_FILTER_THRESHOLD = 8;

const KNOCKOUT_ROUNDS = new Set([
  'round_of_32',
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'third_place',
  'final',
]);

const BRACKET_ROUNDS = new Set([
  'round_of_32',
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'final',
]);

export default {
  name: 'TournamentMatchCenter',
  components: {
    TournamentBracket,
    TournamentStandings,
    MatchDetailView,
    ModalOverlay,
    TournamentHeroCard,
    TournamentMatchRow,
  },
  setup() {
    const authStore = useAuthStore();
    const bracketFollows = useBracketFollows();
    const { isEnabled: pushEnabled } = usePushNotifications();

    const tournaments = ref([]);
    const loading = ref(true);
    const error = ref(null);

    // ── season selector ──
    // Tournaments are scoped to a season; the view defaults to the newest
    // season and lets the user switch back to prior seasons (same idiom as
    // the Table / Matches tabs).
    const seasons = ref([]);
    const selectedSeasonId = ref(null);

    const selectedId = ref(null);
    const selected = ref(null);
    const matchesLoading = ref(false);

    const teamFilter = ref('');
    const ageGroupFilter = ref(null);

    // ── view mode + bracket / standings selectors ──
    const viewMode = ref('list'); // 'list' | 'bracket' | 'standings'
    const bracketAgeGroupId = ref(null);
    const bracketGroup = ref(null);
    const standingsAgeGroupId = ref(null);
    const standingsGroup = ref(null);

    // ── inline match detail (preview) navigation ──
    // When set, MatchDetailView replaces the tournament page (same pattern
    // as MatchesView). Back button clears it.
    const selectedMatchId = ref(null);
    const viewMatch = match => {
      selectedMatchId.value = match.id;
    };
    const handleBackFromMatchDetail = () => {
      selectedMatchId.value = null;
    };

    // ── helpers ──

    // Day-band heading: "Sat 29 Aug". The relative label ("Today" /
    // "Tomorrow") is rendered beside it, not instead of it — a parent still
    // wants the date they can put in a calendar.
    const formatDayBand = d => {
      if (!d) return 'Date TBD';
      return new Date(String(d).slice(0, 10) + 'T00:00:00').toLocaleDateString(
        'en-US',
        { weekday: 'short', day: 'numeric', month: 'short' }
      );
    };

    const relativeDay = d => relativeDayLabel(d);

    // ── data ──

    const formatSeasonDates = season => {
      if (!season?.start_date || !season?.end_date) return '';
      const startYear = new Date(season.start_date).getFullYear();
      const endYear = new Date(season.end_date).getFullYear();
      return `${startYear}-${endYear}`;
    };

    const fetchSeasons = async () => {
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons`,
          { method: 'GET' }
        );
        // Newest first, so seasons[0] is the fallback default.
        const sorted = (data || []).sort(
          (a, b) => new Date(b.start_date) - new Date(a.start_date)
        );
        seasons.value = sorted;
        // Default to the admin-set current season, else newest.
        const current = sorted.find(s => s.is_current) || sorted[0];
        if (current && selectedSeasonId.value == null) {
          selectedSeasonId.value = current.id;
        }
      } catch (err) {
        // Seasons are a secondary filter; a failure here should not blank the
        // whole view. Fall back to the unfiltered tournament list (no season
        // selector) rather than surfacing a page-level error.
        console.error('Error fetching seasons:', err);
      }
    };

    const fetchTournaments = async () => {
      try {
        loading.value = true;
        error.value = null;
        const url = new URL(`${getApiBaseUrl()}/api/tournaments`);
        if (selectedSeasonId.value != null) {
          url.searchParams.set('season_id', selectedSeasonId.value);
        }
        const data = await authStore.apiRequest(url.toString(), {
          method: 'GET',
        });
        // Live first, then what is about to start, then the rest of the
        // calendar, then what is finished — so the selector opens on the
        // tournament a visitor is most likely here for, and so does the
        // default selection below.
        tournaments.value = (data || [])
          .slice()
          .sort((a, b) => compareByStatus(a, b));
        if (tournaments.value.length > 0) {
          await selectTournament(tournaments.value[0].id);
        } else {
          selectedId.value = null;
          selected.value = null;
        }
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const selectTournament = async id => {
      selectedId.value = id;
      matchesLoading.value = true;
      teamFilter.value = '';
      ageGroupFilter.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments/${id}`,
          { method: 'GET' }
        );
        selected.value = data;
      } catch (err) {
        error.value = err.message;
      } finally {
        matchesLoading.value = false;
      }
    };

    // ── filtered + sectioned matches ──

    const availableAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (m.age_group && !seen.has(m.age_group.id)) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const filteredMatches = computed(() => {
      let matches = selected.value?.matches ?? [];
      if (ageGroupFilter.value !== null) {
        matches = matches.filter(m => m.age_group?.id === ageGroupFilter.value);
      }
      if (!teamFilter.value) return matches;
      const q = teamFilter.value.toLowerCase();
      return matches.filter(
        m =>
          m.home_team?.name?.toLowerCase().includes(q) ||
          m.away_team?.name?.toLowerCase().includes(q)
      );
    });

    // Sort key used across all three sections: ascending by match_date first,
    // then by scheduled_kickoff within the day, then by id as a stable
    // tiebreaker. Matches without a scheduled_kickoff still group correctly
    // because the date sort still applies; they fall to the bottom of the
    // day in id-order.
    const byKickoffAsc = (a, b) => {
      const da = a.match_date || '';
      const db = b.match_date || '';
      if (da !== db) return da < db ? -1 : 1;
      const ka = a.scheduled_kickoff || '';
      const kb = b.scheduled_kickoff || '';
      if (ka !== kb) return ka < kb ? -1 : 1;
      return (a.id || 0) - (b.id || 0);
    };

    const groupStageMatches = computed(() =>
      filteredMatches.value
        .filter(m => m.tournament_round === 'group_stage')
        .slice()
        .sort(byKickoffAsc)
    );

    // Knockout: round first (R32 → R16 → QF → SF → 3rd → Final), then
    // chronological within the round. This keeps the visual flow of the
    // tournament progression intact while still ordering within each round.
    const knockoutMatches = computed(() => {
      const order = [
        'round_of_32',
        'round_of_16',
        'quarterfinal',
        'semifinal',
        'third_place',
        'final',
      ];
      return filteredMatches.value
        .filter(m => KNOCKOUT_ROUNDS.has(m.tournament_round))
        .slice()
        .sort((a, b) => {
          const r =
            order.indexOf(a.tournament_round) -
            order.indexOf(b.tournament_round);
          return r !== 0 ? r : byKickoffAsc(a, b);
        });
    });

    const untaggedMatches = computed(() =>
      filteredMatches.value
        .filter(
          m =>
            !m.tournament_round ||
            (!KNOCKOUT_ROUNDS.has(m.tournament_round) &&
              m.tournament_round !== 'group_stage')
        )
        .slice()
        .sort(byKickoffAsc)
    );

    // ── who is viewing ──
    // A parent follows a club across age groups, so club is the primary
    // identity and team is the fallback for accounts that only carry team_id.
    // Signed out, both are null and every highlight silently switches off.
    // `unref` rather than `.value`: the store exposes these as computed refs,
    // but a caller (or a test double) may hand over plain ids, and an account
    // with neither simply has none.
    const myClubId = computed(() => unref(authStore.userClubId) ?? null);
    const myTeamId = computed(() => unref(authStore.userTeamId) ?? null);

    // ── inline scoring ──
    // Scores arrive round by round during a tournament weekend, so the edit
    // affordance lives on the row itself rather than behind the Admin panel.
    // One row at a time is in flight; the id is what the row watches to know
    // its own write finished.
    const savingMatchId = ref(null);
    const saveErrorMatchId = ref(null);
    const saveError = ref('');

    const canEditMatchRow = match =>
      canEditMatch(match, {
        isAdmin: unref(authStore.isAdmin),
        isClubManager: unref(authStore.isClubManager),
        isTeamManager: unref(authStore.isTeamManager),
        clubId: myClubId.value,
        teamId: myTeamId.value,
      });

    const applyMatchUpdate = updated => {
      if (!selected.value?.matches || !updated?.id) return;
      const index = selected.value.matches.findIndex(m => m.id === updated.id);
      if (index === -1) return;
      // Keep the row's display fields (nested team + club objects) — the PATCH
      // response carries the match, not the tournament view's joins.
      selected.value.matches[index] = {
        ...selected.value.matches[index],
        home_score: updated.home_score,
        away_score: updated.away_score,
        home_penalty_score: updated.home_penalty_score,
        away_penalty_score: updated.away_penalty_score,
        match_status: updated.match_status ?? updated.status,
      };
      selected.value = {
        ...selected.value,
        matches: [...selected.value.matches],
      };
    };

    const saveScore = async payload => {
      const match = payload?.match;
      if (!match) return;
      savingMatchId.value = match.id;
      saveErrorMatchId.value = null;
      saveError.value = '';

      const body = {
        home_score: payload.home_score,
        away_score: payload.away_score,
        // A score entered here is a result, not a plan. Anything already
        // beyond "scheduled" (live, forfeit) keeps the status it has.
        ...(match.match_status === 'scheduled' || match.match_status == null
          ? { match_status: 'completed' }
          : {}),
      };
      if (payload.home_penalty_score != null) {
        body.home_penalty_score = payload.home_penalty_score;
        body.away_penalty_score = payload.away_penalty_score;
      }

      try {
        const updated = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${match.id}`,
          { method: 'PATCH', body: JSON.stringify(body) }
        );
        applyMatchUpdate(updated ?? { id: match.id, ...body });
      } catch (err) {
        saveErrorMatchId.value = match.id;
        saveError.value = err?.message || 'Could not save the score.';
      } finally {
        savingMatchId.value = null;
      }
    };

    // The filter input is only worth its row once the list is long enough to
    // need it. Kept visible while a filter is active so it can be cleared.
    const showTeamFilter = computed(
      () =>
        (selected.value?.matches?.length ?? 0) > TEAM_FILTER_THRESHOLD ||
        !!teamFilter.value
    );

    // The three sections, each already sorted, then grouped into days. Empty
    // sections drop out so a tournament with no knockout stage shows no
    // "Knockout Rounds" heading over nothing.
    const listSections = computed(() =>
      [
        {
          key: 'group',
          title: 'Group Stage',
          matches: groupStageMatches.value,
          showRoundChip: false,
          showGroupChip: true,
        },
        {
          key: 'knockout',
          title: 'Knockout Rounds',
          matches: knockoutMatches.value,
          showRoundChip: true,
          showGroupChip: true,
        },
        {
          key: 'untagged',
          title: 'Matches',
          matches: untaggedMatches.value,
          showRoundChip: false,
          showGroupChip: false,
        },
      ]
        .filter(section => section.matches.length > 0)
        .map(section => ({
          ...section,
          days: groupMatchesByDay(section.matches),
        }))
    );

    // Which part of the tournament is actually happening, for the status
    // ribbon. Null when nothing is in flight — the ribbon then shows only the
    // tournament's own state rather than inventing a stage.
    const stageLabel = computed(() => {
      const matches = selected.value?.matches ?? [];
      if (matches.length === 0) return null;
      const live = matches.filter(m => m.match_status === 'in_progress');
      const pool = live.length > 0 ? live : matches;
      const hasKnockout = pool.some(m =>
        KNOCKOUT_ROUNDS.has(m.tournament_round)
      );
      const hasGroup = pool.some(m => m.tournament_round === 'group_stage');
      if (hasKnockout && !hasGroup) return 'Knockout rounds';
      if (hasGroup && !hasKnockout) return 'Group stage';
      return null;
    });

    // True when the tournament has more than one age group represented in
    // its matches — drives whether each row should show the age-group chip.
    // For single-age tournaments (e.g. NAC = U14-only) the chip is pure
    // noise, since the tournament header already states the age group.
    const showAgeChip = computed(() => availableAgeGroups.value.length > 1);

    // ── bracket-mode computed state ──

    // True when the selected tournament has at least one match tagged with
    // a single-elimination bracket round (drives the List|Bracket toggle).
    const hasBracketRounds = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.some(m => BRACKET_ROUNDS.has(m.tournament_round));
    });

    const bracketAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (m.age_group && BRACKET_ROUNDS.has(m.tournament_round)) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const bracketGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const groups = new Set();
      for (const m of matches) {
        if (
          BRACKET_ROUNDS.has(m.tournament_round) &&
          (bracketAgeGroupId.value == null ||
            m.age_group?.id === bracketAgeGroupId.value) &&
          m.tournament_group
        ) {
          groups.add(m.tournament_group);
        }
      }
      // Stable order: Championship first if present, then alphabetical.
      const arr = [...groups];
      arr.sort((a, b) => {
        if (a === 'Championship') return -1;
        if (b === 'Championship') return 1;
        return a.localeCompare(b);
      });
      return arr;
    });

    const bracketMatches = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.filter(
        m =>
          BRACKET_ROUNDS.has(m.tournament_round) &&
          (bracketAgeGroupId.value == null ||
            m.age_group?.id === bracketAgeGroupId.value) &&
          (bracketGroup.value == null ||
            m.tournament_group === bracketGroup.value)
      );
    });

    // Seed defaults when a tournament loads or its match set changes.
    watch(
      () => selected.value?.matches,
      () => {
        if (!hasBracketRounds.value) return;
        if (
          bracketAgeGroupId.value == null &&
          bracketAgeGroups.value.length > 0
        ) {
          bracketAgeGroupId.value = bracketAgeGroups.value[0].id;
        }
        if (bracketGroup.value == null && bracketGroups.value.length > 0) {
          bracketGroup.value = bracketGroups.value[0];
        }
      },
      { immediate: true }
    );

    // If user changes age group and the prior bracket group isn't available
    // for the new age group, fall back to the first available.
    watch(bracketAgeGroupId, () => {
      if (
        bracketGroup.value != null &&
        !bracketGroups.value.includes(bracketGroup.value)
      ) {
        bracketGroup.value = bracketGroups.value[0] ?? null;
      }
    });

    // ── bracket follow toggle ──
    // A user can follow the currently-selected bracket (tournament + group +
    // age group) to get a push at fulltime for every match in it. Gated on
    // being signed in with push enabled, mirroring team-follow buttons.
    //
    // The same (tournament, group, age) tuple is selectable in two views:
    // the knockout Bracket view (bracketGroup/bracketAgeGroupId) and the
    // group-stage Standings view (standingsGroup/standingsAgeGroupId) — e.g.
    // NAC "Bracket A" is a group-stage pool that only renders in Standings.
    // So we expose a follow toggle in BOTH, built from one factory.
    const makeBracketFollow = (groupRef, ageRef) => {
      const can = computed(
        () =>
          authStore.isAuthenticated.value &&
          pushEnabled.value &&
          selectedId.value != null &&
          groupRef.value != null &&
          ageRef.value != null
      );
      const isFollowed = computed(() =>
        bracketFollows.isFollowing(
          selectedId.value,
          groupRef.value,
          ageRef.value
        )
      );
      const toggle = () => {
        if (!can.value) return;
        return bracketFollows.toggle(
          selectedId.value,
          groupRef.value,
          ageRef.value
        );
      };
      // A bracket is selected and the user is signed in, but push isn't on yet —
      // so `can` is false and the button is hidden. Surface a hint instead of
      // showing nothing, pointing them at the profile to enable notifications.
      const needsPush = computed(
        () =>
          authStore.isAuthenticated.value &&
          !pushEnabled.value &&
          selectedId.value != null &&
          groupRef.value != null &&
          ageRef.value != null
      );
      return { can, isFollowed, toggle, needsPush };
    };

    const bracketFollow = makeBracketFollow(bracketGroup, bracketAgeGroupId);
    const canFollowBracket = bracketFollow.can;
    const isBracketFollowed = bracketFollow.isFollowed;
    const toggleBracketFollow = bracketFollow.toggle;
    const bracketNeedsPush = bracketFollow.needsPush;

    const standingsFollow = makeBracketFollow(
      standingsGroup,
      standingsAgeGroupId
    );
    const canFollowStandingsBracket = standingsFollow.can;
    const isStandingsBracketFollowed = standingsFollow.isFollowed;
    const toggleStandingsBracketFollow = standingsFollow.toggle;
    const standingsNeedsPush = standingsFollow.needsPush;

    // ── standings-mode computed state ──
    // Same pattern as bracket-mode, but keyed off group_stage matches
    // grouped by `tournament_group` (e.g. 'U14 Boys Diamond Bracket A').

    const hasStandingsRounds = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.some(
        m => m.tournament_round === 'group_stage' && m.tournament_group
      );
    });

    const standingsAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (
          m.age_group &&
          m.tournament_round === 'group_stage' &&
          m.tournament_group
        ) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const standingsGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const groups = new Set();
      for (const m of matches) {
        if (
          m.tournament_round === 'group_stage' &&
          m.tournament_group &&
          (standingsAgeGroupId.value == null ||
            m.age_group?.id === standingsAgeGroupId.value)
        ) {
          groups.add(m.tournament_group);
        }
      }
      return [...groups].sort((a, b) => a.localeCompare(b));
    });

    const standingsMatches = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.filter(
        m =>
          m.tournament_round === 'group_stage' &&
          m.tournament_group &&
          (standingsAgeGroupId.value == null ||
            m.age_group?.id === standingsAgeGroupId.value) &&
          (standingsGroup.value == null ||
            m.tournament_group === standingsGroup.value)
      );
    });

    watch(
      () => selected.value?.matches,
      () => {
        if (!hasStandingsRounds.value) return;
        if (
          standingsAgeGroupId.value == null &&
          standingsAgeGroups.value.length > 0
        ) {
          standingsAgeGroupId.value = standingsAgeGroups.value[0].id;
        }
        if (standingsGroup.value == null && standingsGroups.value.length > 0) {
          standingsGroup.value = standingsGroups.value[0];
        }
      },
      { immediate: true }
    );

    watch(standingsAgeGroupId, () => {
      if (
        standingsGroup.value != null &&
        !standingsGroups.value.includes(standingsGroup.value)
      ) {
        standingsGroup.value = standingsGroups.value[0] ?? null;
      }
    });

    // Refetch tournaments whenever the season changes.
    watch(selectedSeasonId, () => {
      fetchTournaments();
    });

    onMounted(async () => {
      await fetchSeasons();
      await fetchTournaments();
      bracketFollows.ensureLoaded();
    });

    return {
      canFollowBracket,
      isBracketFollowed,
      toggleBracketFollow,
      bracketNeedsPush,
      canFollowStandingsBracket,
      isStandingsBracketFollowed,
      toggleStandingsBracketFollow,
      standingsNeedsPush,
      tournaments,
      seasons,
      selectedSeasonId,
      formatSeasonDates,
      loading,
      error,
      selectedId,
      selected,
      matchesLoading,
      teamFilter,
      ageGroupFilter,
      availableAgeGroups,
      filteredMatches,
      groupStageMatches,
      knockoutMatches,
      untaggedMatches,
      formatDayBand,
      relativeDay,
      myClubId,
      myTeamId,
      canEditMatchRow,
      saveScore,
      savingMatchId,
      saveErrorMatchId,
      saveError,
      showTeamFilter,
      listSections,
      stageLabel,
      selectTournament,
      viewMode,
      hasBracketRounds,
      bracketAgeGroups,
      bracketAgeGroupId,
      bracketGroups,
      bracketGroup,
      bracketMatches,
      hasStandingsRounds,
      standingsAgeGroups,
      standingsAgeGroupId,
      standingsGroups,
      standingsGroup,
      standingsMatches,
      selectedMatchId,
      viewMatch,
      handleBackFromMatchDetail,
      showAgeChip,
    };
  },
};
</script>
