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
    >{{ label }}</span
  >
</template>

<script setup>
import { computed } from 'vue';

/**
 * What state a match is in — and nothing else (SB-886).
 *
 * The old inline block rendered "Preview" as the `v-else` arm here, styled as a
 * link. It sat in the status column, so an unplayed match appeared to have a
 * status of "Preview"; and it was redundant, because the whole row already
 * navigates to the match. Status now means status.
 */
const props = defineProps({
  status: { type: String, default: null },
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

const entry = computed(() => STATUSES[props.status] ?? null);
// An unrecognised status renders nothing rather than guessing. Absent state is
// absent — it is not "Scheduled".
const label = computed(() => entry.value?.label ?? null);
const tone = computed(() => entry.value?.tone ?? 'text-fg-muted');
const isLive = computed(() => props.status === 'in_progress');
</script>
