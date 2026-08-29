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

const props = defineProps({
  homeScore: { type: Number, default: null },
  awayScore: { type: Number, default: null },
  homePenaltyScore: { type: Number, default: null },
  awayPenaltyScore: { type: Number, default: null },
  // Optional: when given, a result is only rendered for a status that can have
  // one. Guards against stored placeholder zeros on unplayed matches (SB-886) —
  // prod carried `DEFAULT 0` on the score columns, so a fixture kicking off
  // tomorrow arrived here as a 0-0 draw. Omitted (null) keeps the old
  // score-presence-only behaviour for callers that have no status to hand.
  status: { type: String, default: null },
});

// Statuses under which a scoreline is real. A live match at 0-0 is a genuine
// scoreline, so it belongs here alongside completed and forfeit. `live` is the
// stored value; `in_progress` is kept as an alias (SB-910).
const SCORABLE = ['completed', 'live', 'in_progress', 'forfeit'];

const played = computed(() => {
  if (props.homeScore == null || props.awayScore == null) return false;
  if (props.status == null) return true;
  return SCORABLE.includes(props.status);
});

const hasPenalties = computed(
  () =>
    played.value &&
    props.homePenaltyScore != null &&
    props.awayPenaltyScore != null
);
</script>
