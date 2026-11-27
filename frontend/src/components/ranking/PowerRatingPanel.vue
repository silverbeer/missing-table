<template>
  <!--
    The Power Rating list (SB-1809) over GET /api/rankings (SB-1808). A
    national list under tier headers only when the run is comparable
    nationally; otherwise one list per conference, never interleaved. The
    coverage note leads, because the list ranks the teams MT has, not MLS
    NEXT. Admin preview until launch: see RankingView.
  -->
  <div data-testid="power-rating-panel">
    <FilterPanel view="ranking" :summary="summaryText" class="mb-6">
      <div data-testid="pr-age-group-filter">
        <h3 class="text-sm font-medium text-fg mb-3">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="age in AGE_GROUPS"
            :key="age"
            type="button"
            @click="selectedAgeGroup = age"
            :class="pillClass(selectedAgeGroup === age)"
            :data-testid="`pr-age-group-${age}`"
          >
            {{ age }}
          </button>
        </div>
      </div>
      <!-- A national run can also be read by conference; a run that is not
           comparable nationally has the conference lists only. -->
      <div v-if="result?.publication?.national" data-testid="pr-view-filter">
        <h3 class="text-sm font-medium text-fg mb-3">View</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="v in VIEWS"
            :key="v.id"
            type="button"
            @click="selectedView = v.id"
            :class="pillClass(servedView === v.id)"
            :data-testid="`pr-view-${v.id}`"
          >
            {{ v.name }}
          </button>
        </div>
      </div>
    </FilterPanel>

    <div
      v-if="loading"
      class="rounded-lg border border-line bg-card p-4 space-y-3 animate-pulse"
      data-testid="pr-skeleton"
      aria-busy="true"
    >
      <div class="h-3 w-3/4 rounded bg-surface-alt"></div>
      <div v-for="r in 6" :key="r" class="h-8 rounded bg-surface-alt"></div>
    </div>

    <div
      v-else-if="error"
      class="rounded-lg border border-line bg-card p-6 text-center"
      data-testid="pr-error"
    >
      <p class="text-sm text-fg mb-3">{{ error }}</p>
      <button
        type="button"
        class="px-4 py-2 text-sm rounded-lg font-medium bg-brand-500 text-white"
        data-testid="pr-retry"
        @click="retry"
      >
        Retry
      </button>
    </div>

    <!-- No run yet is an answer (200 with a reason), not a failure. -->
    <div
      v-else-if="isEmpty"
      class="rounded-lg border border-line bg-card p-6 text-center"
      data-testid="pr-empty"
    >
      <p class="text-base font-semibold text-fg">No Power Rating yet</p>
      <p
        v-if="result?.reason"
        class="mt-1 text-sm text-fg-muted"
        data-testid="pr-empty-reason"
      >
        {{ result.reason }}
      </p>
    </div>

    <template v-else-if="result">
      <section
        class="min-w-0 rounded-lg border border-line bg-card p-4"
        data-testid="pr-list"
      >
        <div class="mb-3 space-y-1">
          <div class="flex flex-wrap items-baseline justify-between gap-x-3">
            <p
              v-if="updated"
              class="text-xs font-medium text-fg-muted"
              data-testid="pr-updated"
            >
              Updated {{ updated }}
            </p>
            <button
              ref="howLink"
              type="button"
              class="ml-auto text-xs font-medium text-brand-600 dark:text-brand-300 hover:underline"
              data-testid="pr-how-link"
              @click="howOpen = true"
            >
              How it works
            </button>
          </div>
          <p
            v-if="result.coverage?.note"
            class="text-xs text-fg-muted break-words"
            data-testid="pr-coverage-note"
          >
            {{ result.coverage.note }}
          </p>
        </div>

        <template v-if="servedView === 'national'">
          <div
            v-for="group in tierGroups"
            :key="group.key"
            class="mt-3 first:mt-0"
            :data-testid="`pr-tier-${group.key}`"
          >
            <h3
              class="border-b border-line pb-1 text-xs font-semibold uppercase tracking-wide text-fg"
              data-testid="pr-tier-header"
            >
              {{ group.label }}
              <span
                v-if="group.hint"
                class="font-normal normal-case tracking-normal text-fg-muted"
                >· {{ group.hint }}</span
              >
            </h3>
            <ol class="divide-y divide-line">
              <PowerRatingRow
                v-for="row in group.rows"
                :key="row.team_id"
                :row="row"
                :rank="row.rank"
                :movement-since="result.movement_since"
                :expanded="openTeamId === row.team_id"
                :panel-id="whyId(row)"
                @toggle="toggleTeam"
              >
                <PowerRatingTeamPanel
                  :id="whyId(row)"
                  :team-id="row.team_id"
                  :team-name="row.team"
                  :age-group="result.age_group || selectedAgeGroup"
                  :league="result.league || LEAGUE"
                  :season="result.season"
                  :pro-academy="row.pro_academy"
                  :cache="teamCache"
                  @view-matches="navigateToTeam(row)"
                  @close="openTeamId = null"
                />
              </PowerRatingRow>
            </ol>
          </div>
        </template>

        <template v-else>
          <nav
            v-if="conferences.length > 0"
            class="flex flex-wrap gap-2 mb-3"
            aria-label="Conferences"
            data-testid="pr-conference-tabs"
          >
            <button
              v-for="conf in conferences"
              :key="conf"
              type="button"
              @click="selectedConference = conf"
              :class="chipClass(activeConference === conf)"
              data-testid="pr-conference-tab"
            >
              {{ conf }}
            </button>
          </nav>
          <p
            v-if="result.publication?.reason"
            class="mb-3 text-xs text-fg-muted break-words"
            data-testid="pr-publication-reason"
          >
            Not yet comparable nationally: {{ result.publication.reason }}
          </p>
          <p
            v-if="conferenceRows.length === 0"
            class="py-6 text-center text-sm text-fg-muted"
            data-testid="pr-no-rows"
          >
            No team in this conference has 6 matches yet
          </p>
          <ol v-else class="divide-y divide-line">
            <PowerRatingRow
              v-for="row in conferenceRows"
              :key="row.team_id"
              :row="row"
              :rank="row.conference_rank"
              :movement-since="result.movement_since"
              :expanded="openTeamId === row.team_id"
              :panel-id="whyId(row)"
              @toggle="toggleTeam"
            >
              <PowerRatingTeamPanel
                :id="whyId(row)"
                :team-id="row.team_id"
                :team-name="row.team"
                :age-group="result.age_group || selectedAgeGroup"
                :league="result.league || LEAGUE"
                :season="result.season"
                :pro-academy="row.pro_academy"
                :cache="teamCache"
                @view-matches="navigateToTeam(row)"
                @close="openTeamId = null"
              />
            </PowerRatingRow>
          </ol>
        </template>
      </section>

      <section
        v-if="unrankedRows.length > 0"
        class="mt-6 min-w-0 rounded-lg border border-line bg-surface-alt/40 p-4 opacity-80"
        data-testid="pr-unranked"
      >
        <h3 class="text-sm font-semibold text-fg mb-2">
          Not ranked yet — under {{ minMatches }} matches
        </h3>
        <ul class="divide-y divide-line">
          <li
            v-for="row in unrankedRows"
            :key="row.team_id"
            class="py-1.5 text-sm"
            data-testid="pr-unranked-row"
          >
            <span class="line-clamp-2 break-words leading-snug text-fg">{{
              row.team
            }}</span>
            <span class="block text-xs text-fg-muted tabular-nums">
              {{ row.conference || 'No conference' }} · {{ row.mp }} of
              {{ row.needed ?? minMatches }} matches
            </span>
          </li>
        </ul>
      </section>
    </template>

    <PowerRatingHowItWorks
      v-if="howOpen"
      :teams-in-pool="result?.coverage?.teams_in_pool ?? null"
      :age-group="result?.age_group || selectedAgeGroup"
      @close="closeHow"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import { filterSummary } from '@/utils/filterSummary';
import { formatUpdated, groupByTier } from '@/utils/powerRating';
import FilterPanel from '../ui/FilterPanel.vue';
import PowerRatingHowItWorks from './PowerRatingHowItWorks.vue';
import PowerRatingRow from './PowerRatingRow.vue';
import PowerRatingTeamPanel from './PowerRatingTeamPanel.vue';

// The Power Rating covers Homegrown U15 to U19 (power-rating.md "Scope").
const AGE_GROUPS = ['U15', 'U16', 'U17', 'U19'];
const LEAGUE = 'Homegrown';
const VIEWS = [
  { id: 'national', name: 'National' },
  { id: 'conference', name: 'By conference' },
];

const emit = defineEmits(['navigate-to-team']);
const authStore = useAuthStore();

const selectedAgeGroup = ref('U15');
// null lets the API pick: national when the run is, conference otherwise.
const selectedView = ref(null);
const selectedConference = ref(null);

const result = ref(null);
const loading = ref(false);
const error = ref('');

// For the ids in a team click; the rankings answer carries names only.
// Optional: a failed read leaves the navigation with a filter fewer.
const lookups = ref({ ageGroups: [], leagues: [], seasons: [] });

// The one row whose "why" panel is open (SB-1810), and the team answers
// already read this session, so reopening a team is not a request.
const openTeamId = ref(null);
const teamCache = new Map();
const whyId = row => `pr-why-${row.team_id}`;
const toggleTeam = row => {
  openTeamId.value = openTeamId.value === row.team_id ? null : row.team_id;
};

// The How it works screen (SB-1811); closing returns focus to its link.
const howOpen = ref(false);
const howLink = ref(null);
const closeHow = async () => {
  howOpen.value = false;
  await nextTick();
  howLink.value?.focus();
};

const pillClass = active => [
  'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
  active
    ? 'bg-brand-500 text-white shadow-sm'
    : 'bg-surface-alt text-fg-muted hover:bg-line',
];
const chipClass = active => [
  'px-3 py-1 text-xs rounded-full font-medium transition-colors',
  active
    ? 'bg-brand-500 text-white shadow-sm'
    : 'bg-surface-alt text-fg-muted hover:bg-line',
];

const summaryText = computed(() =>
  filterSummary([selectedAgeGroup.value, LEAGUE])
);

// The view the API served, which may not be the one asked for.
const servedView = computed(() => result.value?.view || 'conference');
const minMatches = computed(() => result.value?.coverage?.min_matches ?? 6);
const updated = computed(() => formatUpdated(result.value?.run?.computed_at));

const tierGroups = computed(() =>
  groupByTier(result.value?.teams, result.value?.tiers)
);

const conferences = computed(() => result.value?.conferences || []);
const activeConference = computed(() =>
  conferences.value.includes(selectedConference.value)
    ? selectedConference.value
    : (conferences.value[0] ?? null)
);

// The API orders the conference view by conference, then conference rank.
const conferenceRows = computed(() =>
  (result.value?.teams || []).filter(
    t =>
      activeConference.value == null || t.conference === activeConference.value
  )
);

const unrankedRows = computed(() => {
  const rows = result.value?.unranked || [];
  if (servedView.value === 'national' || activeConference.value == null) {
    return rows;
  }
  return rows.filter(r => r.conference === activeConference.value);
});

const isEmpty = computed(() => {
  const r = result.value;
  if (!r) return false;
  return !(r.teams && r.teams.length) && !(r.unranked && r.unranked.length);
});

// A filter change mid-flight must not let the older answer land last.
let requestId = 0;

const fetchRankings = async () => {
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  const params = new URLSearchParams({
    league: LEAGUE,
    age_group: selectedAgeGroup.value,
  });
  if (selectedView.value) params.set('view', selectedView.value);
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/rankings?${params}`
    );
    if (id !== requestId) return;
    result.value = data;
  } catch (err) {
    if (id !== requestId) return;
    result.value = null;
    error.value = err?.message || 'The Power Rating is unavailable right now.';
  } finally {
    if (id === requestId) loading.value = false;
  }
};

const fetchList = async path => {
  try {
    const data = await authStore.apiRequest(`${getApiBaseUrl()}${path}`);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    console.error(`Error fetching ${path}:`, err);
    return [];
  }
};

const fetchLookups = async () => {
  const [ageGroups, leagues, seasons] = await Promise.all([
    fetchList('/api/age-groups'),
    fetchList('/api/leagues'),
    fetchList('/api/seasons'),
  ]);
  lookups.value = { ageGroups, leagues, seasons };
};

const lookupsMissing = () =>
  Object.values(lookups.value).some(list => list.length === 0);

const retry = () => {
  fetchRankings();
  if (lookupsMissing()) fetchLookups();
};

const idByName = (list, name) =>
  name ? (list.find(item => item?.name === name)?.id ?? null) : null;

// The payload shape LeaderboardsPanel emits, so Matches opens on this team
// at the age group, league and season the run rated.
const navigateToTeam = row => {
  const r = result.value;
  emit('navigate-to-team', {
    teamId: row.team_id,
    clubId: row.club_id ?? null,
    ageGroupId: idByName(
      lookups.value.ageGroups,
      r?.age_group || selectedAgeGroup.value
    ),
    leagueId: idByName(lookups.value.leagues, r?.league || LEAGUE),
    divisionId: null,
    seasonId: idByName(lookups.value.seasons, r?.season),
  });
};

watch([selectedAgeGroup, selectedView], () => {
  openTeamId.value = null;
  fetchRankings();
});
watch(selectedConference, () => {
  openTeamId.value = null;
});

onMounted(() => {
  fetchRankings();
  fetchLookups();
});
</script>
