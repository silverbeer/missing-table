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
        <p
          v-if="indexNotice"
          class="text-sm mt-3"
          data-testid="tournament-index-notice"
        >
          {{ indexNotice }}
        </p>
      </div>

      <!-- Season index (SB-1767): one card per tournament. -->
      <TournamentIndex
        v-else-if="selectedId == null"
        :tournaments="tournaments"
        :notice="indexNotice"
        @open="openTournament"
      />

      <template v-else>
        <!-- Back to the index, and a compact switcher between this season's
             tournaments when there is more than one. -->
        <div class="mb-6 flex items-center gap-2 min-w-0">
          <button
            type="button"
            class="shrink-0 px-3 py-2 rounded-full text-sm font-medium text-brand-600 dark:text-brand-300 hover:text-brand-800 dark:hover:text-brand-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            data-testid="tournament-back-to-index"
            @click="backToIndex"
          >
            ← All tournaments
          </button>
          <div
            v-if="tournaments.length > 1"
            class="flex gap-2 overflow-x-auto min-w-0 pb-1"
            data-testid="tournament-switcher"
          >
            <button
              v-for="t in tournaments"
              :key="t.id"
              type="button"
              @click="openTournament(t.id)"
              :aria-current="selectedId === t.id ? 'page' : undefined"
              :class="[
                'shrink-0 whitespace-nowrap px-4 py-2 rounded-full text-sm font-medium transition-colors',
                selectedId === t.id
                  ? 'bg-brand-600 text-white'
                  : 'bg-card border border-line text-fg hover:border-brand-400',
              ]"
            >
              {{ t.name }}
            </button>
          </div>
        </div>

        <!-- Tournament detail -->
        <div v-if="selected">
          <!-- Hero card: says where the tournament is in its own life before
               it says what is in it. -->
          <TournamentHeroCard
            :tournament="selected"
            :matches="selected.matches || []"
            :total-matches="isLargeTournament ? selected.match_count : null"
            :my-club-id="myClubId"
            :my-team-id="myTeamId"
            :stage-label="stageLabel"
            @select-match="viewMatch"
          >
            <template #actions>
              <!-- View toggle: List always shown; Bracket / Standings shown
                   based on match round shape. Neither is offered for a large
                   tournament: both are built from every match at once, which
                   a paged tournament never holds (SB-1749). -->
              <div
                v-if="
                  !isLargeTournament && (hasBracketRounds || hasStandingsRounds)
                "
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
          <!-- Tournament Match of the Day (SB-1560): today's pick only, in
               every view, for the age group being viewed (SB-1750). All Ages
               stacks one banner per age group. No pick renders nothing. -->
          <TournamentMotdBanner
            v-for="entry in todayMotds"
            :key="entry.key"
            :pick="entry.pick"
            :live-match="entry.liveMatch"
            day-label="Today"
            @select-match="viewMatch"
          />
          <!-- Match loading -->
          <div v-if="matchesLoading" class="flex justify-center py-8">
            <div
              class="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600"
            ></div>
          </div>

          <template v-else-if="selected.matches && viewMode === 'list'">
            <!-- Large tournament: filters are applied by the server, and an
                 age group is always selected (SB-1749). -->
            <TournamentFilters
              v-if="isLargeTournament"
              :age-groups="filterAgeGroups"
              :selected-age-group-id="viewedAgeGroupId"
              :groups="filterGroups"
              :selected-group="selectedGroupKey"
              @update:age-group="setAgeGroup"
              @update:group="setGroup"
            />
            <!-- Age group filter -->
            <div
              v-else-if="availableAgeGroups.length > 1"
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

            <!-- Large tournament: the page for the current filters is on its
                 way, failed, or is genuinely empty. Empty is said in words —
                 a spinner would promise matches that are not coming. -->
            <template v-if="isLargeTournament">
              <div
                v-if="pageLoading"
                class="flex justify-center py-8"
                data-testid="tournament-page-loading"
              >
                <div
                  class="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600"
                ></div>
              </div>
              <div
                v-else-if="pageError && selected.matches.length === 0"
                class="text-center py-10 text-fg-muted"
                data-testid="tournament-page-error"
              >
                {{ pageError }}
                <button
                  type="button"
                  class="ml-1 text-brand-600 dark:text-brand-300 hover:text-brand-800 dark:hover:text-brand-200"
                  @click="reloadPage"
                >
                  Try again
                </button>
              </div>
              <div
                v-else-if="selected.matches.length === 0"
                class="text-center py-10 text-fg-muted"
                data-testid="tournament-page-empty"
              >
                {{ largeEmptyText }}
              </div>
            </template>
            <!-- No matches -->
            <div
              v-else-if="selected.matches.length === 0"
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

            <!-- Group stage / Showcase / Knockout / Placement finals /
                 Consolation / Matches, each grouped by day. -->
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
                    :is-motd="motdMatchIds.includes(match.id)"
                    @select="viewMatch"
                    @save="saveScore"
                  />
                </div>
              </div>
            </div>

            <!-- Large tournament: how much of the filtered list is on screen,
                 and the next page. No count is shown until the server has
                 given one. -->
            <div
              v-if="isLargeTournament && selected.matches.length > 0"
              class="mt-2 mb-6 flex flex-wrap items-center justify-center gap-3 text-sm text-fg-muted"
              data-testid="tournament-page-footer"
            >
              <span v-if="filteredTotal != null" data-testid="tournament-shown">
                Showing {{ selected.matches.length }} of {{ filteredTotal }}
                {{ filteredTotal === 1 ? 'match' : 'matches' }}
              </span>
              <span v-if="pageError" data-testid="tournament-more-error">{{
                pageError
              }}</span>
              <button
                v-if="hasMoreMatches"
                type="button"
                :disabled="loadingMore"
                data-testid="tournament-load-more"
                class="px-4 py-1.5 rounded-full text-sm font-medium bg-card border border-line text-fg hover:border-brand-400 disabled:opacity-50"
                @click="loadMore"
              >
                {{ loadingMore ? 'Loading…' : 'Load more' }}
              </button>
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
              :motd-match-ids="motdMatchIds"
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
import { ref, computed, onMounted, onUnmounted, unref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';
import TournamentBracket from './TournamentBracket.vue';
import TournamentStandings from './TournamentStandings.vue';
import MatchDetailView from './MatchDetailView.vue';
import ModalOverlay from './ui/ModalOverlay.vue';
import TournamentHeroCard from './TournamentHeroCard.vue';
import TournamentMatchRow from './TournamentMatchRow.vue';
import TournamentMotdBanner from './TournamentMotdBanner.vue';
import TournamentFilters from './TournamentFilters.vue';
import TournamentIndex from './TournamentIndex.vue';
import { parseTournamentPath, tournamentPath } from '../utils/tournamentRoute';
import { useLiveRowSync } from '@/composables/useLiveRowSync';
import { useBracketFollows } from '../composables/useBracketFollows';
import { usePushNotifications } from '../composables/usePushNotifications';
import {
  isLargeTournament as isLargeSummary,
  useTournamentMatches,
} from '../composables/useTournamentMatches';
import {
  compareByStatus,
  groupMatchesByDay,
  localDateKey,
  relativeDayLabel,
} from '../utils/tournamentStatus';
import { canEditMatch } from '../utils/matchPermissions';
import { pickAgeGroupId, picksForView } from '../utils/tournamentMotd';
import {
  BRACKET_ROUNDS,
  KNOCKOUT_ROUNDS,
  KNOCKOUT_ROUND_ORDER,
} from '../utils/tournamentRounds';
import {
  STAGE_ROUNDS,
  STAGE_ROUND_SECTIONS,
  buildStageSections,
} from '../utils/tournamentStages';

// Past this many matches the list is long enough that a team filter earns its
// row. Below it the input is larger than the thing it filters.
const TEAM_FILTER_THRESHOLD = 8;

export default {
  name: 'TournamentMatchCenter',
  components: {
    TournamentBracket,
    TournamentStandings,
    MatchDetailView,
    ModalOverlay,
    TournamentHeroCard,
    TournamentMatchRow,
    TournamentMotdBanner,
    TournamentFilters,
    TournamentIndex,
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

    // How the matches are fetched — one detail call, or paged and filtered
    // by the server for a large tournament — lives in the composable
    // (SB-1749). `selected` is its tournament: the header plus whichever
    // matches are loaded.
    const tournamentMatches = useTournamentMatches();
    const selectedId = ref(null);
    const selected = tournamentMatches.tournament;
    const matchesLoading = ref(false);
    const isLargeTournament = tournamentMatches.isLarge;

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

    // ── URLs (SB-1767) ──
    // `/tournaments` is the season index, `/tournaments/<id>` one tournament.
    // App.vue decides that a path opens this tab; this component decides
    // index vs detail. Nothing here ever writes the page title or a preview
    // tag: the title stays "Missing Table" whatever is open.
    const indexNotice = ref(null);
    // Async work outlives the component (tab switched, signed out) and must
    // not write the address bar or fetch for a page nobody is on.
    let isUnmounted = false;
    // Bumped by every navigation: card, switcher, "All tournaments", back /
    // forward, season change. A continuation that finds it moved belongs to
    // a navigation the visitor has already left, and does nothing.
    let navSeq = 0;
    // Bumped by every list fetch; only the latest one owns `loading` and
    // `tournaments`.
    let listSeq = 0;
    // The visitor asked for the index, so a one-tournament season is not
    // opened for them again until the season changes or the tab is re-entered.
    let indexRequested = false;
    // The open tournament was pushed on top of the index: "All tournaments"
    // is then a history.back(), so the back button and the link agree.
    let pushedFromIndex = false;
    // The season was set to follow a link into another season, not by the
    // selector, so its watcher must not fetch or reset the URL.
    let seasonSetByLink = false;

    const currentRoute = () => parseTournamentPath(window.location?.pathname);
    const writeHistory = (method, path) => {
      if (isUnmounted) return;
      try {
        window.history[method](null, '', path);
      } catch (err) {
        // A sandboxed frame can refuse; the page still works without a URL.
        console.error('Error updating the address bar:', err);
      }
    };

    const fetchTournamentList = async seasonId => {
      const url = new URL(`${getApiBaseUrl()}/api/tournaments`);
      if (seasonId != null) url.searchParams.set('season_id', seasonId);
      const data = await authStore.apiRequest(url.toString(), {
        method: 'GET',
      });
      // Live first, then what is about to start, then the rest of the
      // calendar, then what is finished — the index reads in that order.
      return (data || []).slice().sort((a, b) => compareByStatus(a, b));
    };

    const showIndex = () => {
      selectedId.value = null;
      selected.value = null;
      motdPicks.value = [];
      viewMode.value = 'list';
      pushedFromIndex = false;
    };

    // No id asked for: the index, except that a season with exactly one
    // tournament opens it — replacing the URL, so back does not land on an
    // index that would only open it again.
    const openDefault = async () => {
      if (tournaments.value.length === 1 && !indexRequested) {
        const id = tournaments.value[0].id;
        // Replaced, not pushed: there is no index behind it to go back to.
        pushedFromIndex = false;
        writeHistory('replaceState', tournamentPath(id));
        await selectTournament(id);
      } else {
        showIndex();
      }
    };

    // An id from the URL. It must be opened from its row in a tournament
    // list — `match_count` there picks small or large mode — so an id in
    // another season is looked up in the unfiltered list, never through the
    // detail endpoint.
    const openFromLink = async (id, seq) => {
      if (
        !tournaments.value.some(t => t.id === id) &&
        selectedSeasonId.value != null
      ) {
        const all = await fetchTournamentList(null);
        if (isUnmounted || seq !== navSeq) return;
        const row = all.find(t => t.id === id);
        if (row && row.season_id != null) {
          if (row.season_id !== selectedSeasonId.value) {
            seasonSetByLink = true;
            selectedSeasonId.value = row.season_id;
          }
          tournaments.value = all.filter(t => t.season_id === row.season_id);
        }
      }
      if (tournaments.value.some(t => t.id === id)) {
        await selectTournament(id);
        return;
      }
      // Unknown, inactive or hidden from this viewer: the same words for
      // each, so a link never confirms that a tournament exists.
      indexNotice.value = "That tournament isn't available.";
      showIndex();
      writeHistory('replaceState', tournamentPath());
    };

    // `wantedId`: an id from the URL, opened once the list can say where it
    // is. Without one the season's default applies.
    const fetchTournaments = async (wantedId = null) => {
      const seq = navSeq;
      const fetchId = ++listSeq;
      const current = () => !isUnmounted && fetchId === listSeq;
      try {
        loading.value = true;
        error.value = null;
        const list = await fetchTournamentList(selectedSeasonId.value);
        if (!current()) return;
        tournaments.value = list;
        // A navigation since this fetch began has already chosen the view.
        if (seq !== navSeq) return;
        if (wantedId != null) {
          await openFromLink(wantedId, seq);
        } else {
          await openDefault();
        }
      } catch (err) {
        if (current()) error.value = err.message;
      } finally {
        if (current()) loading.value = false;
      }
    };

    // A card or a switcher chip. Pushed, so back returns to where it was
    // opened from.
    const openTournament = async id => {
      if (id === selectedId.value) return;
      navSeq += 1;
      const fromIndex = selectedId.value == null;
      writeHistory('pushState', tournamentPath(id));
      pushedFromIndex = fromIndex;
      indexNotice.value = null;
      await selectTournament(id);
    };

    const backToIndex = () => {
      navSeq += 1;
      indexRequested = true;
      indexNotice.value = null;
      if (pushedFromIndex) {
        window.history.back();
      } else {
        writeHistory('pushState', tournamentPath());
      }
      showIndex();
    };

    // Back / forward between the index and a tournament. A path outside the
    // tab is App.vue's to handle: it switches tabs, and this unmounts.
    const onPopState = () => {
      const route = currentRoute();
      if (!route) return;
      navSeq += 1;
      indexNotice.value = null;
      pushedFromIndex = false;
      if (route.kind === 'index') {
        indexRequested = true;
        showIndex();
        return;
      }
      if (route.id === selectedId.value) return;
      if (tournaments.value.some(t => t.id === route.id)) {
        selectTournament(route.id);
      } else {
        fetchTournaments(route.id);
      }
    };

    // ── Tournament Match of the Day (SB-1560) ──
    // Picks are decoration on top of the schedule: a failed fetch leaves the
    // page as it would be with no picks, never on an error path.
    const motdPicks = ref([]);
    const fetchMotd = async id => {
      if (isUnmounted) return;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments/${id}/motd`,
          { method: 'GET' }
        );
        // A late answer for a tournament the visitor has already left.
        if (isUnmounted || selectedId.value !== id) return;
        motdPicks.value = Array.isArray(data?.picks) ? data.picks : [];
      } catch (err) {
        console.error('Error fetching match of the day:', err);
      }
    };
    // Today's picks for the age group on screen (SB-1750): one, or none —
    // never another age group's. All Ages shows every pick for the day.
    // `liveMatch`: the tournament payload's copy is kept current by realtime;
    // the pick's embedded match is a snapshot from when it loaded, and all
    // there is when the match is not on the loaded page.
    const todayMotds = computed(() =>
      picksForView(motdPicks.value, {
        today: localDateKey(),
        ageGroupId: viewedAgeGroupId.value,
      }).map((pick, i) => {
        const id = pick.match?.id;
        return {
          key: `${pickAgeGroupId(pick) ?? 'none'}-${id ?? i}`,
          pick,
          liveMatch:
            id == null
              ? null
              : (selected.value?.matches ?? []).find(m => m.id === id) || null,
        };
      })
    );
    const motdMatchIds = computed(() =>
      motdPicks.value.map(p => p.match?.id).filter(id => id != null)
    );

    const selectTournament = async id => {
      if (isUnmounted) return;
      selectedId.value = id;
      motdPicks.value = [];
      fetchMotd(id);
      matchesLoading.value = true;
      teamFilter.value = '';
      ageGroupFilter.value = null;
      // The row from the tournament list carries the exact match_count the
      // scale switch reads, and is the header of a large tournament.
      const summary = tournaments.value.find(t => t.id === id) ?? { id };
      // A large tournament has no bracket or standings view to stay on.
      if (isLargeSummary(summary)) viewMode.value = 'list';
      try {
        await tournamentMatches.load(summary);
      } catch (err) {
        error.value = err.message;
      } finally {
        matchesLoading.value = false;
      }
    };

    // A tournament page is often left open through a match — on a phone, on a
    // sideline. Realtime keeps live rows current, and a refetch when the tab
    // comes back covers whatever the socket missed (SB-909). Without this the
    // page shows the score it loaded with until someone reloads it.
    const selectedMatches = computed(() => selected.value?.matches ?? []);

    const refreshSelected = async () => {
      if (selectedId.value == null) return;
      fetchMotd(selectedId.value);
      try {
        await tournamentMatches.refresh();
      } catch (err) {
        // A background refresh that fails leaves what is on screen alone —
        // it is stale, not wrong, and blanking the page would be worse.
        console.error('Error refreshing tournament:', err);
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

    // The age group on screen, in either mode: the server-side selection of a
    // large tournament, the chip of a small one (null = All Ages). The
    // bracket and standings views of a small tournament each keep their own
    // age selection (SB-1750).
    const viewedAgeGroupId = computed(() => {
      if (isLargeTournament.value) {
        return tournamentMatches.selectedAgeGroupId.value;
      }
      if (viewMode.value === 'bracket') return bracketAgeGroupId.value;
      if (viewMode.value === 'standings') return standingsAgeGroupId.value;
      return ageGroupFilter.value;
    });

    // What an empty page of a large tournament says. An age group with no
    // matches is a real state, so it is named, not left spinning.
    const largeEmptyText = computed(() => {
      if (tournamentMatches.selectedGroup.value) {
        return 'No matches match this filter.';
      }
      const age = tournamentMatches.ageGroups.value.find(
        ag => ag.id === tournamentMatches.selectedAgeGroupId.value
      );
      return age?.name
        ? `No ${age.name} matches entered yet.`
        : 'No matches entered yet.';
    });

    // In a large tournament the server has already applied the filters, so
    // the loaded rows are the filtered rows.
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
      const order = KNOCKOUT_ROUND_ORDER;
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

    // Showcase, placement finals and consolation: one section per stage
    // label within each round (SB-1749).
    const stageSections = round =>
      buildStageSections(
        filteredMatches.value.slice().sort(byKickoffAsc),
        STAGE_ROUND_SECTIONS.find(s => s.round === round)
      ).map(section => ({
        ...section,
        showRoundChip: false,
        showGroupChip: false,
      }));

    const untaggedMatches = computed(() =>
      filteredMatches.value
        .filter(
          m =>
            !m.tournament_round ||
            (!KNOCKOUT_ROUNDS.has(m.tournament_round) &&
              !STAGE_ROUNDS.has(m.tournament_round) &&
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

    // Realtime UPDATEs land in the same merge the inline editor uses: the
    // payload carries raw `matches` columns, so the row's joined team and
    // age-group objects have to survive it (SB-909).
    useLiveRowSync(selectedMatches, applyMatchUpdate, {
      onReturn: refreshSelected,
    });

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
    // Not offered for a large tournament: it would search only the rows
    // loaded so far and read as "this team is not here".
    const showTeamFilter = computed(
      () =>
        !isLargeTournament.value &&
        ((selected.value?.matches?.length ?? 0) > TEAM_FILTER_THRESHOLD ||
          !!teamFilter.value)
    );

    // The sections, each already sorted, then grouped into days. Empty
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
        ...stageSections('showcase'),
        {
          key: 'knockout',
          title: 'Knockout Rounds',
          matches: knockoutMatches.value,
          showRoundChip: true,
          showGroupChip: true,
        },
        ...stageSections('placement_final'),
        ...stageSections('consolation'),
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
      // 'live' is the stored status; 'in_progress' is an alias kept for older
      // payloads. Matching only the alias meant a tournament with a match
      // actually under way never counted as live (SB-910).
      const live = matches.filter(m =>
        ['live', 'in_progress'].includes(m.match_status)
      );
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

    // Refetch tournaments whenever the season changes, and show that season's
    // index. The default season set on mount is skipped — onMounted fetches
    // for it, and a second fetch would race the id from the URL.
    watch(selectedSeasonId, (seasonId, previous) => {
      if (previous == null) return;
      if (seasonSetByLink) {
        seasonSetByLink = false;
        return;
      }
      navSeq += 1;
      indexRequested = false;
      indexNotice.value = null;
      writeHistory('replaceState', tournamentPath());
      fetchTournaments();
    });

    onMounted(async () => {
      const route = currentRoute();
      const wantedId = route?.kind === 'detail' ? route.id : null;
      if (!route) {
        // Entered from the tab bar: the address bar says where we are.
        writeHistory('replaceState', tournamentPath());
      }
      window.addEventListener('popstate', onPopState);
      const mountSeq = navSeq;
      await fetchSeasons();
      if (isUnmounted) return;
      if (navSeq === mountSeq) {
        await fetchTournaments(wantedId);
      } else if (listSeq === 0) {
        // Back / forward to the index while seasons loaded: that season's
        // index, without the link that is no longer in the address bar.
        await fetchTournaments();
      }
      if (isUnmounted) return;
      bracketFollows.ensureLoaded();
    });

    // Leaving the tab: a reload of the next tab must not reopen a tournament.
    // A path outside the tab (back to another page) is left as it is. After
    // this, nothing still in flight writes the address bar or fetches.
    onUnmounted(() => {
      window.removeEventListener('popstate', onPopState);
      if (currentRoute()) writeHistory('replaceState', '/');
      isUnmounted = true;
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
      openTournament,
      backToIndex,
      indexNotice,
      isLargeTournament,
      viewedAgeGroupId,
      filterAgeGroups: tournamentMatches.ageGroups,
      filterGroups: tournamentMatches.groups,
      selectedGroupKey: tournamentMatches.selectedGroup,
      filteredTotal: tournamentMatches.total,
      hasMoreMatches: tournamentMatches.hasMore,
      pageLoading: tournamentMatches.pageLoading,
      loadingMore: tournamentMatches.loadingMore,
      pageError: tournamentMatches.pageError,
      largeEmptyText,
      setAgeGroup: tournamentMatches.setAgeGroup,
      setGroup: tournamentMatches.setGroup,
      loadMore: tournamentMatches.loadMore,
      reloadPage: tournamentMatches.reloadPage,
      todayMotds,
      motdMatchIds,
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
