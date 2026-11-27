<template>
  <!--
    One Power Rating row (SB-1809). Conference, MP and the record sit under
    the name so the rating column always has room at 360px (SB-1795); the
    name clamps to two lines rather than pushing it off screen. Tapping it
    opens the team's "why" panel (the default slot) inline beneath it
    (SB-1810); Escape closes it and returns focus to the row.
  -->
  <li @keydown.esc="expanded && close()">
    <button
      ref="rowButton"
      type="button"
      class="w-full flex items-center gap-2 py-2 text-left hover:bg-surface-alt rounded focus:outline-none focus:bg-surface-alt"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-controls="panelId"
      data-testid="pr-row"
      @click="$emit('toggle', row)"
    >
      <span
        class="w-8 shrink-0 text-right text-sm tabular-nums text-fg-muted"
        data-testid="pr-rank"
        >{{ rank ?? '—' }}</span
      >
      <ClubLogo
        :logo-url="row.club_logo_url || ''"
        :name="row.team"
        size="xs"
      />
      <span class="flex-1 min-w-0">
        <span
          class="line-clamp-2 break-words text-sm font-medium leading-snug text-brand-600 dark:text-brand-300"
          data-testid="pr-team"
          >{{ row.team }}</span
        >
        <span class="block text-xs text-fg-muted" data-testid="pr-meta">
          <span data-testid="pr-conference">{{ conferenceLine }}</span>
          <span class="tabular-nums" data-testid="pr-record">
            · MP {{ row.mp }} · {{ row.w }}-{{ row.d }}-{{ row.l }}</span
          >
        </span>
        <span
          v-if="chips.length > 0"
          class="mt-0.5 flex flex-wrap gap-1"
          data-testid="pr-badges"
        >
          <span
            v-for="chip in chips"
            :key="chip.key"
            :title="chip.title"
            class="inline-block rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide bg-surface-alt text-fg-muted"
            :data-testid="`pr-badge-${chip.key}`"
            >{{ chip.label }}</span
          >
        </span>
      </span>
      <span class="shrink-0 min-w-[3.5rem] text-right">
        <span
          class="block text-sm font-semibold tabular-nums text-fg"
          data-testid="pr-rating"
          >{{ formatRating(row.rating) }}</span
        >
        <span
          v-if="movement"
          :class="[
            'block text-xs tabular-nums',
            MOVEMENT_CLASS[movement.direction],
          ]"
          data-testid="pr-movement"
          >{{ movement.text }}</span
        >
      </span>
    </button>
    <slot v-if="expanded" />
  </li>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import ClubLogo from '../shared/ClubLogo.vue';
import {
  BADGES,
  formatMovement,
  formatRating,
  ordinal,
} from '@/utils/powerRating';

const props = defineProps({
  row: { type: Object, required: true },
  /** The rank shown: national in the national view, conference otherwise. */
  rank: { type: Number, default: null },
  movementSince: { type: Object, default: null },
  expanded: { type: Boolean, default: false },
  /** The id of the panel this row opens, for aria-controls. */
  panelId: { type: String, default: null },
});

const emit = defineEmits(['toggle']);
const rowButton = ref(null);

const close = () => emit('toggle', props.row);

// Closing from inside the panel (Escape, Close) would drop focus on the
// page; hand it back to the row.
watch(
  () => props.expanded,
  (open, was) => {
    if (was && !open) {
      nextTick(() => {
        const active = document.activeElement;
        if (!active || active === document.body) rowButton.value?.focus();
      });
    }
  }
);

const MOVEMENT_CLASS = {
  up: 'text-green-600 dark:text-green-400',
  down: 'text-red-600 dark:text-red-400',
  flat: 'text-fg-muted',
  new: 'text-fg-muted',
};

const conferenceLine = computed(() => {
  const conf = props.row.conference || 'No conference';
  const place = ordinal(props.row.conference_rank);
  return place ? `${conf} · ${place}` : conf;
});

const movement = computed(() =>
  formatMovement(
    props.row.rank_change_7d,
    props.row.rating_change_7d,
    props.movementSince
  )
);

const chips = computed(() => {
  const out = (props.row.badges || [])
    .filter(b => BADGES[b])
    .map(b => ({ key: b, ...BADGES[b] }));
  if (props.row.pro_academy) {
    out.push({
      key: 'pro_academy',
      label: 'Pro academy',
      title: 'Pro academy: information only, it does not change the rating',
    });
  }
  return out;
});
</script>
