<template>
  <span
    v-if="label"
    :class="[
      'text-xs font-medium whitespace-nowrap',
      tone,
      { 'animate-pulse': isLive },
    ]"
    data-testid="match-status-label"
    :data-status="status"
    :data-missing-result="missingResult ? 'true' : 'false'"
    >{{ label }}</span
  >
</template>

<script setup>
import { computed } from 'vue';
import { isMissingResult } from '../../utils/tournamentStatus';

/**
 * What state a match is in — and nothing else (SB-886).
 *
 * The old inline block rendered "Preview" as the `v-else` arm here, styled as a
 * link. It sat in the status column, so an unplayed match appeared to have a
 * status of "Preview"; and it was redundant, because the whole row already
 * navigates to the match. Status now means status.
 *
 * SB-889: "Scheduled" is a claim about the future, so it is wrong on a fixture
 * whose date has passed. Given a `matchDate`, a past-dated `scheduled` / `tbd`
 * match reads "Not reported" instead.
 */
const props = defineProps({
  status: { type: String, default: null },
  // How the score is being recorded: 'live' once live scoring started, else
  // 'manual'. A match can be under way in both senses, and only the first
  // deserves a pulsing "Live" — the pulse promises a clock and an event feed
  // that a manually-updated match does not have (SB-910).
  scoringMode: { type: String, default: 'manual' },
  // Optional. Without it the component cannot tell a future fixture from a
  // stale one, so it keeps the plain status — back-compat for any caller with
  // no date to hand.
  matchDate: { type: String, default: null },
});

const STATUSES = {
  completed: { label: 'Final', tone: 'text-green-600 dark:text-green-400' },
  forfeit: { label: 'Forfeit', tone: 'text-fg-muted' },
  // `live` is the value the database stores; `in_progress` is an alias kept
  // for any payload still using it. Before SB-910 only the alias was listed,
  // so a match that was actually under way rendered no status label at all.
  live: { label: 'Live', tone: 'text-red-600 dark:text-red-400' },
  in_progress: { label: 'Live', tone: 'text-red-600 dark:text-red-400' },
  cancelled: { label: 'Cancelled', tone: 'text-red-500 dark:text-red-400' },
  postponed: { label: 'Postponed', tone: 'text-fg-muted' },
  scheduled: { label: 'Scheduled', tone: 'text-fg-muted' },
  tbd: { label: 'TBD', tone: 'text-fg-muted' },
};

const missingResult = computed(() =>
  isMissingResult({ match_status: props.status, match_date: props.matchDate })
);

const isUnderWay = computed(
  () => props.status === 'live' || props.status === 'in_progress'
);

// Under way but nobody live-scoring: it is in progress, and saying "Live" would
// promise a feed that does not exist.
const isLiveScored = computed(
  () => isUnderWay.value && props.scoringMode === 'live'
);

const entry = computed(() => {
  if (isUnderWay.value && !isLiveScored.value) {
    return { label: 'In Progress', tone: 'text-amber-600 dark:text-amber-400' };
  }
  return STATUSES[props.status] ?? null;
});

// An unrecognised status renders nothing rather than guessing. Absent state is
// absent — it is not "Scheduled".
const label = computed(() => {
  if (!entry.value) return null;
  return missingResult.value ? 'Not reported' : entry.value.label;
});

// Deliberately the same muted tone as "Scheduled" rather than a warning
// colour. For most of the archive this is an expected state, not a fault, and
// painting 81 rows amber would read as an outage.
const tone = computed(() => {
  if (!entry.value) return 'text-fg-muted';
  return missingResult.value ? 'text-fg-muted italic' : entry.value.tone;
});

const isLive = isLiveScored;
</script>
