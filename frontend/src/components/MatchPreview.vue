<template>
  <div class="match-preview bg-slate-800 rounded-lg p-3">
    <!-- Loading -->
    <div
      v-if="loading"
      class="flex flex-col items-center justify-center py-12"
      data-testid="preview-loading"
    >
      <div
        class="w-8 h-8 border-2 border-slate-500 border-t-blue-400 rounded-full animate-spin mb-3"
      ></div>
      <p class="text-slate-400 text-sm">Loading match preview...</p>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="flex flex-col items-center justify-center py-12 text-center"
      data-testid="preview-error"
    >
      <div
        class="w-10 h-10 rounded-full bg-red-900/50 flex items-center justify-center text-red-400 font-bold mb-3"
      >
        !
      </div>
      <p class="text-slate-400 text-sm mb-3">{{ error }}</p>
      <button
        @click="fetchPreview"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Retry
      </button>
    </div>

    <!-- Content -->
    <div v-else-if="preview" data-testid="preview-content">
      <!-- Tab bar -->
      <div class="border-b border-slate-600 mb-4">
        <nav class="flex space-x-1" aria-label="Match preview sections">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :data-testid="`tab-${tab.id}`"
            :class="[
              'py-2 px-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
              activeTab === tab.id
                ? 'border-blue-400 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-500',
            ]"
          >
            {{ tab.label }}
            <span
              v-if="tab.count !== null"
              class="ml-1 text-xs px-1.5 py-0.5 rounded-full"
              :class="
                activeTab === tab.id
                  ? 'bg-blue-900/50 text-blue-300'
                  : 'bg-slate-700 text-slate-400'
              "
              >{{ tab.count }}</span
            >
          </button>
        </nav>
      </div>

      <!-- ── Recent Form ── -->
      <div v-if="activeTab === 'form'" data-testid="tab-panel-form">
        <!-- Both teams empty -->
        <div
          v-if="
            preview.home_team_recent.length === 0 &&
            preview.away_team_recent.length === 0
          "
          class="flex flex-col items-center py-10 text-slate-500"
          data-testid="form-empty"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            class="w-10 h-10 mb-3 text-slate-600"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.5"
              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <p class="text-sm">No recent form data available.</p>
        </div>
        <!-- At least one team has data -->
        <div v-else class="grid grid-cols-2 gap-3">
          <!-- Home team column -->
          <div>
            <h3
              class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2 truncate"
            >
              {{ homeTeamName }}
            </h3>
            <div
              v-if="preview.home_team_recent.length === 0"
              class="text-xs text-slate-500 italic"
            >
              No recent matches
            </div>
            <div
              v-for="match in preview.home_team_recent"
              :key="match.id"
              class="mb-2"
              data-testid="home-recent-match"
            >
              <MatchResultCard :match="match" :perspectiveTeamId="homeTeamId" />
            </div>
          </div>

          <!-- Away team column -->
          <div>
            <h3
              class="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2 truncate"
            >
              {{ awayTeamName }}
            </h3>
            <div
              v-if="preview.away_team_recent.length === 0"
              class="text-xs text-slate-500 italic"
            >
              No recent matches
            </div>
            <div
              v-for="match in preview.away_team_recent"
              :key="match.id"
              class="mb-2"
              data-testid="away-recent-match"
            >
              <MatchResultCard :match="match" :perspectiveTeamId="awayTeamId" />
            </div>
          </div>
        </div>
      </div>

      <!-- ── Common Opponents ── -->
      <div v-else-if="activeTab === 'common'" data-testid="tab-panel-common">
        <div
          v-if="preview.common_opponents.length === 0"
          class="flex flex-col items-center py-10 text-slate-500"
          data-testid="common-empty"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            class="w-10 h-10 mb-3 text-slate-600"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.5"
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          <p class="text-sm">No common opponents found this season.</p>
        </div>
        <div
          v-for="opp in preview.common_opponents"
          :key="opp.opponent_id"
          class="mb-5"
          data-testid="common-opponent-section"
        >
          <!-- Opponent header -->
          <div
            class="flex items-center gap-2 mb-2 pb-1 border-b border-slate-600"
          >
            <span class="inline-block w-2 h-2 rounded-full bg-slate-500"></span>
            <span class="text-sm font-semibold text-slate-200"
              >vs {{ opp.opponent_name }}</span
            >
          </div>

          <div class="grid grid-cols-2 gap-3">
            <!-- Home team vs opponent -->
            <div>
              <p class="text-xs text-slate-400 mb-1 truncate">
                {{ homeTeamName }}
              </p>
              <div
                v-if="opp.home_team_matches.length === 0"
                class="text-xs text-slate-500 italic"
              >
                No matches
              </div>
              <div
                v-for="match in opp.home_team_matches"
                :key="match.id"
                class="mb-1.5"
              >
                <MatchResultCard
                  :match="match"
                  :perspectiveTeamId="homeTeamId"
                  compact
                />
              </div>
            </div>
            <!-- Away team vs opponent -->
            <div>
              <p class="text-xs text-slate-400 mb-1 truncate">
                {{ awayTeamName }}
              </p>
              <div
                v-if="opp.away_team_matches.length === 0"
                class="text-xs text-slate-500 italic"
              >
                No matches
              </div>
              <div
                v-for="match in opp.away_team_matches"
                :key="match.id"
                class="mb-1.5"
              >
                <MatchResultCard
                  :match="match"
                  :perspectiveTeamId="awayTeamId"
                  compact
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Head-to-Head ── -->
      <div v-else-if="activeTab === 'h2h'" data-testid="tab-panel-h2h">
        <div
          v-if="preview.head_to_head.length === 0"
          class="flex flex-col items-center py-10 text-slate-500"
          data-testid="h2h-empty"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            class="w-10 h-10 mb-3 text-slate-600"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.5"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <p class="text-sm">No previous meetings found.</p>
        </div>

        <!-- Summary row -->
        <div
          v-if="preview.head_to_head.length > 0"
          class="flex justify-around text-center mb-4 p-3 bg-slate-700/50 rounded-lg"
        >
          <div>
            <span class="block text-xl font-bold text-blue-400">{{
              h2hStats.homeWins
            }}</span>
            <span class="text-xs text-slate-400 truncate block max-w-[80px]">{{
              homeTeamName
            }}</span>
          </div>
          <div>
            <span class="block text-xl font-bold text-slate-400">{{
              h2hStats.draws
            }}</span>
            <span class="text-xs text-slate-400">Draws</span>
          </div>
          <div>
            <span class="block text-xl font-bold text-red-400">{{
              h2hStats.awayWins
            }}</span>
            <span class="text-xs text-slate-400 truncate block max-w-[80px]">{{
              awayTeamName
            }}</span>
          </div>
        </div>

        <!-- Match list -->
        <div
          v-for="match in preview.head_to_head"
          :key="match.id"
          class="mb-2"
          data-testid="h2h-match"
        >
          <H2HMatchRow
            :match="match"
            :homeTeamId="homeTeamId"
            :awayTeamId="awayTeamId"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

// ─── Sub-components defined inline ────────────────────────────────────────────

/**
 * MatchResultCard - compact match result from one team's perspective.
 * Shows: W/L/D chip | score | opponent name | date
 */
const MatchResultCard = {
  props: {
    match: { type: Object, required: true },
    perspectiveTeamId: { type: Number, required: true },
    compact: { type: Boolean, default: false },
  },
  setup(props) {
    const outcome = computed(() => {
      const m = props.match;
      if (m.home_score === null || m.away_score === null) return null;
      const isHome = m.home_team_id === props.perspectiveTeamId;
      const teamScore = isHome ? m.home_score : m.away_score;
      const oppScore = isHome ? m.away_score : m.home_score;
      if (teamScore > oppScore) return 'W';
      if (teamScore < oppScore) return 'L';
      return 'D';
    });

    const opponent = computed(() => {
      const m = props.match;
      return m.home_team_id === props.perspectiveTeamId
        ? m.away_team_name
        : m.home_team_name;
    });

    const scoreDisplay = computed(() => {
      const m = props.match;
      if (m.home_score === null || m.away_score === null) return '- : -';
      return `${m.home_score} - ${m.away_score}`;
    });

    const outcomeClass = computed(() => {
      if (outcome.value === 'W') return 'bg-green-900/60 text-green-400';
      if (outcome.value === 'L') return 'bg-red-900/60 text-red-400';
      if (outcome.value === 'D') return 'bg-slate-600 text-slate-300';
      return 'bg-slate-600 text-slate-400';
    });

    const formattedDate = computed(() => {
      if (!props.match.match_date) return '';
      const d = new Date(props.match.match_date + 'T00:00:00');
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    return { outcome, opponent, scoreDisplay, outcomeClass, formattedDate };
  },
  template: `
    <div class="flex items-center gap-1.5 p-1.5 rounded bg-slate-700 border border-slate-600 text-xs">
      <span :class="['font-bold w-4 text-center shrink-0', outcomeClass]" style="border-radius:2px">
        {{ outcome ?? '?' }}
      </span>
      <span class="font-mono font-semibold text-slate-200 shrink-0">{{ scoreDisplay }}</span>
      <span class="text-slate-300 truncate flex-1">{{ opponent }}</span>
      <span class="text-slate-500 shrink-0">{{ formattedDate }}</span>
    </div>
  `,
};

/**
 * H2HMatchRow - single head-to-head match row.
 * Shows home and away team with score centred, plus season and date.
 */
const H2HMatchRow = {
  props: {
    match: { type: Object, required: true },
    homeTeamId: { type: Number, required: true },
    awayTeamId: { type: Number, required: true },
  },
  setup(props) {
    const formattedDate = computed(() => {
      if (!props.match.match_date) return '';
      const d = new Date(props.match.match_date + 'T00:00:00');
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    });

    const winnerClass = teamId => {
      const m = props.match;
      if (m.home_score === null || m.away_score === null) return '';
      const isHome = m.home_team_id === teamId;
      const score = isHome ? m.home_score : m.away_score;
      const opp = isHome ? m.away_score : m.home_score;
      if (score > opp) return 'font-bold text-white';
      if (score < opp) return 'text-slate-500';
      return 'text-slate-300';
    };

    return { formattedDate, winnerClass };
  },
  template: `
    <div class="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-xs">
      <span :class="['flex-1 text-right truncate', winnerClass(match.home_team_id)]">{{ match.home_team_name }}</span>
      <span class="font-mono font-semibold text-slate-200 shrink-0 bg-slate-600 px-2 py-0.5 rounded">
        {{ match.home_score ?? '-' }} – {{ match.away_score ?? '-' }}
      </span>
      <span :class="['flex-1 truncate', winnerClass(match.away_team_id)]">{{ match.away_team_name }}</span>
      <div class="text-right shrink-0 ml-2">
        <div class="text-slate-400">{{ formattedDate }}</div>
        <div class="text-slate-500">{{ match.season_name }}</div>
      </div>
    </div>
  `,
};

// ─── Props ────────────────────────────────────────────────────────────────────

const props = defineProps({
  homeTeamId: { type: Number, required: true },
  homeTeamName: { type: String, default: 'Home Team' },
  awayTeamId: { type: Number, required: true },
  awayTeamName: { type: String, default: 'Away Team' },
  /** Season ID scopes "recent form" and "common opponents". Null = all seasons. */
  seasonId: { type: Number, default: null },
  /** Optional: narrow to a specific age group */
  ageGroupId: { type: Number, default: null },
  /** How many recent matches to fetch per team */
  recentCount: { type: Number, default: 5 },
});

// ─── State ────────────────────────────────────────────────────────────────────

const authStore = useAuthStore();
const preview = ref(null);
const loading = ref(false);
const error = ref(null);
const activeTab = ref('form');

// ─── Tabs ────────────────────────────────────────────────────────────────────

const tabs = computed(() => [
  { id: 'form', label: 'Recent Form', count: null },
  {
    id: 'common',
    label: 'Common Opponents',
    count: preview.value ? (preview.value.common_opponents?.length ?? 0) : null,
  },
  {
    id: 'h2h',
    label: 'Head-to-Head',
    count: preview.value ? (preview.value.head_to_head?.length ?? 0) : null,
  },
]);

// ─── Head-to-head summary stats ───────────────────────────────────────────────

const h2hStats = computed(() => {
  if (!preview.value) return { homeWins: 0, awayWins: 0, draws: 0 };
  return preview.value.head_to_head.reduce(
    (acc, m) => {
      if (m.home_score === null || m.away_score === null) return acc;
      const homeIsOurHome = m.home_team_id === props.homeTeamId;
      const homeScore = homeIsOurHome ? m.home_score : m.away_score;
      const awayScore = homeIsOurHome ? m.away_score : m.home_score;
      if (homeScore > awayScore) acc.homeWins++;
      else if (homeScore < awayScore) acc.awayWins++;
      else acc.draws++;
      return acc;
    },
    { homeWins: 0, awayWins: 0, draws: 0 }
  );
});

// ─── Data fetching ───────────────────────────────────────────────────────────

async function fetchPreview() {
  loading.value = true;
  error.value = null;
  try {
    const params = new URLSearchParams();
    if (props.seasonId) params.set('season_id', props.seasonId);
    if (props.ageGroupId) params.set('age_group_id', props.ageGroupId);
    params.set('recent_count', props.recentCount);

    const url = `${getApiBaseUrl()}/api/matches/preview/${props.homeTeamId}/${props.awayTeamId}?${params}`;
    const data = await authStore.apiRequest(url);
    // Normalize to guarantee expected arrays are always present
    preview.value = {
      home_team_id: data?.home_team_id ?? props.homeTeamId,
      away_team_id: data?.away_team_id ?? props.awayTeamId,
      home_team_recent: Array.isArray(data?.home_team_recent)
        ? data.home_team_recent
        : [],
      away_team_recent: Array.isArray(data?.away_team_recent)
        ? data.away_team_recent
        : [],
      common_opponents: Array.isArray(data?.common_opponents)
        ? data.common_opponents
        : [],
      head_to_head: Array.isArray(data?.head_to_head) ? data.head_to_head : [],
    };

    // Auto-select the tab with the most content
    const { home_team_recent, away_team_recent, common_opponents } =
      preview.value;
    const hasForm = home_team_recent.length > 0 || away_team_recent.length > 0;
    if (hasForm) {
      activeTab.value = 'form';
    } else if (common_opponents.length > 0) {
      activeTab.value = 'common';
    } else {
      activeTab.value = 'h2h';
    }
  } catch (err) {
    error.value = err.message || 'Failed to load match preview';
  } finally {
    loading.value = false;
  }
}

// Refetch when key props change
watch(
  () => [props.homeTeamId, props.awayTeamId, props.seasonId, props.ageGroupId],
  () => fetchPreview(),
  { immediate: false }
);

onMounted(fetchPreview);
</script>
