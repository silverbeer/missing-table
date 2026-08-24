<template>
  <span
    :class="[
      'px-2 sm:px-2.5 py-0.5 rounded-md shrink-0 tabular-nums text-sm sm:text-base',
      played
        ? 'bg-surface-alt text-fg border border-line font-bold'
        : 'text-fg-muted font-medium',
    ]"
    data-testid="score-pill"
  >
    <template v-if="played">
      {{ homeScore }}&thinsp;–&thinsp;{{ awayScore
      }}<span
        v-if="hasPenalties"
        class="ml-1 text-xs font-semibold opacity-80"
        data-testid="score-pill-penalties"
        >({{ homePenaltyScore }}&thinsp;–&thinsp;{{
          awayPenaltyScore
        }}&nbsp;pk)</span
      >
    </template>
    <template v-else>vs</template>
  </span>
</template>

<script setup>
import { computed } from 'vue';

/**
 * Match score, or "vs" when the match has not been played.
 *
 * Numerals are the UI font with tabular figures rather than a monospace face:
 * mono read as terminal output, and tabular-nums already keeps columns of
 * scores aligned. Thin spaces around the en dash stop "0–0" from closing up.
 *
 * The chip uses theme tokens (surface-alt / fg / line), not a fixed near-black:
 * a hard-coded dark pill sat heavily on the light table and disappeared into
 * the background in dark mode.
 *
 * Absent is not zero (see CLAUDE.md): a match with no score shows "vs", never
 * "0 – 0". Both sides must be present for a score to render.
 */
const props = defineProps({
  homeScore: { type: Number, default: null },
  awayScore: { type: Number, default: null },
  homePenaltyScore: { type: Number, default: null },
  awayPenaltyScore: { type: Number, default: null },
});

const played = computed(
  () => props.homeScore != null && props.awayScore != null
);

const hasPenalties = computed(
  () => props.homePenaltyScore != null && props.awayPenaltyScore != null
);
</script>
