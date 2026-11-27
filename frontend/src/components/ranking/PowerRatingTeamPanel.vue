<template>
  <!--
    The team's "why" panel (SB-1810), opened inline under its Power Rating
    row, over GET /api/rankings/teams/{id} (SB-1808): the 3 matches that
    moved the rating most, strength of schedule with its denominator, the
    rating over time, and the badges in words. Answers are cached by the
    list for the session, so reopening a team is not a request.
  -->
  <div
    :id="id"
    class="mx-1 mb-2 rounded-lg border border-line bg-surface-alt/40 p-3"
    role="region"
    :aria-label="`Why ${teamName} is rated where it is`"
    data-testid="pr-why"
  >
    <div
      v-if="loading"
      class="space-y-2 animate-pulse"
      data-testid="pr-why-skeleton"
      aria-busy="true"
    >
      <div class="h-3 w-1/2 rounded bg-surface-alt"></div>
      <div v-for="r in 3" :key="r" class="h-6 rounded bg-surface-alt"></div>
      <div class="h-8 rounded bg-surface-alt"></div>
    </div>

    <div v-else-if="error" class="text-center" data-testid="pr-why-error">
      <p class="text-sm text-fg mb-2">{{ error }}</p>
      <button
        type="button"
        class="px-3 py-1.5 text-sm rounded-lg font-medium bg-brand-500 text-white"
        data-testid="pr-why-retry"
        @click="load(true)"
      >
        Retry
      </button>
    </div>

    <p
      v-else-if="team && !team.in_run"
      class="text-sm text-fg-muted break-words"
      data-testid="pr-why-reason"
    >
      {{ team.reason }}
    </p>

    <div v-else-if="team" class="space-y-3 text-sm">
      <p
        v-if="team.needed != null"
        class="text-xs text-fg-muted"
        data-testid="pr-why-needed"
      >
        Needs {{ team.needed }} more
        {{ team.needed === 1 ? 'match' : 'matches' }} to be ranked.
      </p>

      <section data-testid="pr-why-movers">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-fg mb-1">
          Results that moved it most
        </h4>
        <ul v-if="movers.length > 0" class="space-y-1.5">
          <li
            v-for="m in movers"
            :key="m.key"
            class="flex items-start gap-2"
            data-testid="pr-why-mover"
          >
            <span class="flex-1 min-w-0">
              <!-- Not clamped: the score ends the line and a long opponent
                   name would clamp it away. -->
              <span
                class="block break-words leading-snug text-fg"
                data-testid="pr-why-mover-headline"
                >{{ m.headline }}</span
              >
              <span
                v-if="m.detail"
                class="block text-xs text-fg-muted"
                data-testid="pr-why-mover-detail"
                >{{ m.detail }}</span
              >
            </span>
            <span
              :class="[
                'shrink-0 font-semibold tabular-nums',
                DELTA_CLASS[m.direction],
              ]"
              data-testid="pr-why-mover-delta"
              >{{ m.delta }}</span
            >
          </li>
        </ul>
        <p v-else class="text-xs text-fg-muted">No rated match yet.</p>
      </section>

      <section v-if="sosText" data-testid="pr-why-sos">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-fg mb-1">
          Strength of schedule
        </h4>
        <p
          class="text-fg tabular-nums break-words"
          data-testid="pr-why-sos-text"
        >
          {{ sosText }}
        </p>
      </section>

      <section v-if="history.length > 0" data-testid="pr-why-history">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-fg mb-1">
          Rating over time
        </h4>
        <div
          v-if="spark"
          class="flex items-center gap-2"
          role="img"
          :aria-label="historyLabel"
          data-testid="pr-why-sparkline"
        >
          <span
            class="shrink-0 text-xs tabular-nums text-fg-muted"
            data-testid="pr-why-history-first"
            >{{ formatRating(history[0].rating) }}</span
          >
          <svg
            viewBox="0 0 200 40"
            preserveAspectRatio="none"
            class="h-10 min-w-0 flex-1 text-brand-500 dark:text-brand-300"
            aria-hidden="true"
          >
            <polyline
              :points="spark.points"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
              stroke-linecap="round"
              vector-effect="non-scaling-stroke"
            />
          </svg>
          <span
            class="shrink-0 text-xs font-semibold tabular-nums text-fg"
            data-testid="pr-why-history-last"
            >{{ formatRating(history[history.length - 1].rating) }}</span
          >
        </div>
        <p
          v-else
          class="text-fg tabular-nums"
          :aria-label="historyLabel"
          data-testid="pr-why-history-single"
        >
          {{ formatRating(history[0].rating) }}
          <span class="text-xs text-fg-muted">· one week rated so far</span>
        </p>
      </section>

      <ul
        v-if="badgeLines.length > 0"
        class="space-y-1 text-xs text-fg-muted"
        data-testid="pr-why-badges"
      >
        <li v-for="b in badgeLines" :key="b.key" class="break-words">
          {{ b.text }}
        </li>
      </ul>
    </div>

    <div class="mt-3 flex items-center justify-between gap-2">
      <button
        type="button"
        class="px-3 py-1.5 text-sm rounded-lg font-medium bg-brand-500 text-white"
        data-testid="pr-why-view-matches"
        @click="$emit('view-matches')"
      >
        View matches
      </button>
      <button
        type="button"
        class="px-3 py-1.5 text-sm rounded-lg font-medium bg-surface-alt text-fg-muted hover:bg-line"
        data-testid="pr-why-close"
        @click="$emit('close')"
      >
        Close
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import {
  BADGE_EXPLANATIONS,
  formatMatchDate,
  formatMover,
  formatRating,
  formatSos,
  sparkline,
} from '@/utils/powerRating';

const props = defineProps({
  id: { type: String, required: true },
  teamId: { type: Number, required: true },
  teamName: { type: String, default: '' },
  ageGroup: { type: String, required: true },
  league: { type: String, required: true },
  season: { type: String, default: null },
  proAcademy: { type: Boolean, default: false },
  /** Answers by request key, owned by the list so they outlive this panel. */
  cache: { type: Map, required: true },
});

defineEmits(['view-matches', 'close']);

const DELTA_CLASS = {
  up: 'text-green-600 dark:text-green-400',
  down: 'text-red-600 dark:text-red-400',
  flat: 'text-fg-muted',
};

const authStore = useAuthStore();
const team = ref(null);
const loading = ref(false);
const error = ref('');
let alive = true;

const params = computed(() => {
  const p = new URLSearchParams({
    age_group: props.ageGroup,
    league: props.league,
  });
  if (props.season) p.set('season', props.season);
  return p;
});
const cacheKey = computed(() => `${props.teamId}?${params.value}`);

const load = async (force = false) => {
  const key = cacheKey.value;
  if (!force && props.cache.has(key)) {
    team.value = props.cache.get(key);
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/rankings/teams/${props.teamId}?${params.value}`
    );
    if (!alive) return;
    props.cache.set(key, data);
    team.value = data;
  } catch (err) {
    if (!alive) return;
    team.value = null;
    error.value = err?.message || 'The Power Rating is unavailable right now.';
  } finally {
    if (alive) loading.value = false;
  }
};

const movers = computed(() =>
  (team.value?.biggest_movers || []).map(m => ({
    key: m.match_id,
    ...formatMover(m),
  }))
);

const sosText = computed(() =>
  formatSos(team.value?.sos, team.value?.conference)
);

const history = computed(() => team.value?.history || []);
const spark = computed(() => sparkline(history.value));

const pointLabel = h =>
  [formatRating(h.rating), formatMatchDate(h.computed_at)]
    .filter(Boolean)
    .join(' on ');

const historyLabel = computed(() => {
  const h = history.value;
  if (h.length === 0) return '';
  if (h.length === 1) return `Rating ${pointLabel(h[0])}, one week rated`;
  return `Rating over ${h.length} weeks, from ${pointLabel(h[0])} to ${pointLabel(h[h.length - 1])}`;
});

const badgeLines = computed(() => {
  const out = (team.value?.badges || [])
    .filter(b => BADGE_EXPLANATIONS[b])
    .map(b => ({ key: b, text: BADGE_EXPLANATIONS[b] }));
  if (team.value?.pro_academy ?? props.proAcademy) {
    out.push({
      key: 'pro_academy',
      text: 'Pro academy: shown for information only, it does not change the rating.',
    });
  }
  return out;
});

onMounted(() => load());
onBeforeUnmount(() => {
  alive = false;
});
</script>
