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
  // Optional. Without it the component cannot tell a future fixture from a
  // stale one, so it keeps the plain status — back-compat for any caller with
  // no date to hand.
  matchDate: { type: String, default: null },
});

const STATUSES = {
  completed: { label: 'Final', tone: 'text-green-600 dark:text-green-400' },
  forfeit: { label: 'Forfeit', tone: 'text-fg-muted' },
  in_progress: { label: 'Live', tone: 'text-red-600 dark:text-red-400' },
  cancelled: { label: 'Cancelled', tone: 'text-red-500 dark:text-red-400' },
  postponed: { label: 'Postponed', tone: 'text-fg-muted' },
  scheduled: { label: 'Scheduled', tone: 'text-fg-muted' },
  tbd: { label: 'TBD', tone: 'text-fg-muted' },
};

const missingResult = computed(() =>
  isMissingResult({ match_status: props.status, match_date: props.matchDate })
);

const entry = computed(() => STATUSES[props.status] ?? null);

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

const isLive = computed(() => props.status === 'in_progress');
</script>
