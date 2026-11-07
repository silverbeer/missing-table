<template>
  <section
    class="mb-4 rounded-lg border border-amber-300 dark:border-amber-700 border-l-4 border-l-amber-400 bg-amber-50 dark:bg-amber-950/40 px-3 sm:px-4 py-3"
    data-testid="motd-banner"
    :data-has-reasons="hasReasons ? 'true' : 'false'"
  >
    <!--
      Tournament Match of the Day (SB-1560).

      One pick per tournament per day, shown only on the day it is for. Unlike
      the Match of the Week strip, this one opens by default: a tournament page
      is the thing the visitor came for, and the pick is the day's headline.

      Three states, by design (CLAUDE.md): no pick renders nothing at all — no
      placeholder, no skeleton; a pick without reasons is the fixture and its
      headline; reasons add the "Why" list.
    -->
    <div class="flex items-center gap-2 mb-1.5">
      <span
        class="text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-300"
      >
        <span aria-hidden="true">◆</span> Match of the Day
      </span>
      <span v-if="dayLabel" class="text-xs text-fg-muted" data-testid="motd-day"
        >· {{ dayLabel }}</span
      >
      <span
        v-if="ageGroupName"
        class="ml-auto text-xs font-medium text-fg-muted"
        data-testid="motd-age"
        >{{ ageGroupName }}</span
      >
    </div>

    <button
      type="button"
      class="w-full text-left group"
      data-testid="motd-fixture"
      @click="$emit('select-match', match)"
    >
      <div
        class="flex flex-wrap items-baseline gap-x-2 text-base sm:text-lg font-bold text-fg group-hover:text-brand-700 dark:group-hover:text-brand-200"
      >
        <span>{{ homeName }}</span>
        <span
          v-if="hasScore"
          class="font-mono tabular-nums"
          data-testid="motd-score"
          >{{ match.home_score }}–{{ match.away_score }}</span
        >
        <span v-else class="text-sm font-medium text-fg-muted">vs</span>
        <span>{{ awayName }}</span>
      </div>
      <p
        v-if="pick.blurb"
        class="mt-0.5 text-sm text-fg"
        data-testid="motd-blurb"
      >
        {{ pick.blurb }}
      </p>
    </button>

    <div v-if="hasReasons" class="mt-2.5" data-testid="motd-reasons">
      <h4
        class="text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200 mb-1"
      >
        Why this is the Match of the Day
      </h4>
      <ul class="space-y-0.5">
        <li
          v-for="(reason, i) in pick.reasons"
          :key="i"
          class="flex gap-2 text-sm text-fg"
          data-testid="motd-reason"
        >
          <span
            class="text-amber-600 dark:text-amber-400 shrink-0"
            aria-hidden="true"
            >▸</span
          >
          <span>{{ reason.text }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  // `{ match_date, blurb, reasons, match }` from GET /api/tournaments/{id}/motd.
  pick: { type: Object, required: true },
  // The tournament's own copy of the match, when the page has it: fresher
  // scores than the pick's snapshot, since realtime keeps the list current.
  liveMatch: { type: Object, default: null },
  dayLabel: { type: String, default: '' },
});

defineEmits(['select-match']);

const match = computed(() => props.liveMatch || props.pick.match || {});

const homeName = computed(
  () => match.value.home_team?.name || match.value.home_team_name || 'TBD'
);
const awayName = computed(
  () => match.value.away_team?.name || match.value.away_team_name || 'TBD'
);
const ageGroupName = computed(
  () => match.value.age_group?.name || match.value.age_group_name || ''
);

// Absent is not zero: an unplayed match shows "vs", never 0–0.
const hasScore = computed(
  () => match.value.home_score != null && match.value.away_score != null
);

// null (never written) and [] (written, empty) both render no "Why" section;
// the distinction lives in the data for the adoption funnel, not on screen.
const hasReasons = computed(
  () => Array.isArray(props.pick.reasons) && props.pick.reasons.length > 0
);
</script>
