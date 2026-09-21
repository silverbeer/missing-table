<template>
  <section
    class="mb-4 last:mb-0"
    data-testid="match-mobile-list"
    :data-section="sectionLabel || 'all'"
  >
    <!-- League header. Sticky so a reader who has scrolled three matchdays
         deep still knows which competition they are looking at — the fact the
         per-row "Type" field used to repeat on every card. -->
    <h3
      v-if="sectionLabel"
      :class="[
        'sticky top-0 z-20 text-white font-bold text-xs tracking-wide py-2 px-3 rounded-lg shadow-sm',
        sectionClass,
      ]"
      data-testid="match-section-header"
    >
      {{ sectionLabel }}
    </h3>

    <div v-for="group in groups" :key="group.key" data-testid="match-day-group">
      <!-- Day header, sitting just under the league header so the two stack
           rather than overlap as the reader scrolls between matchdays. -->
      <h4
        class="sticky z-10 bg-surface-alt/95 backdrop-blur text-[11px] font-semibold uppercase tracking-wide text-fg-muted py-1.5 px-3 border-b border-line"
        :style="{ top: dayHeaderTop }"
        data-testid="match-day-header"
      >
        {{ group.label }}
      </h4>

      <ul class="space-y-1.5 py-1.5">
        <MatchListRow
          v-for="match in group.matches"
          :key="match.id"
          :match="match"
          :can-edit="canEdit(match)"
          :is-admin="isAdmin"
          :highlight="isHighlighted(match)"
          @view="$emit('view', $event)"
          @more="openSheet"
        />
      </ul>
    </div>

    <MatchActionsSheet
      v-if="sheetMatch"
      :match="sheetMatch"
      :can-edit="canEdit(sheetMatch)"
      :is-admin="isAdmin"
      @close="closeSheet"
      @view="onSheetView"
      @edit="onSheetEdit"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import MatchListRow from './MatchListRow.vue';
import MatchActionsSheet from './MatchActionsSheet.vue';
import { groupMatchesByDate } from '../../utils/matchGrouping';

/**
 * The phone match list: sticky league and day headers over compact rows
 * (SB-1101).
 *
 * This replaced four near-identical blocks of card markup in MatchesView —
 * Homegrown, Academy, Other and My Club — which had already drifted apart from
 * each other (My Club's actions were text links, the rest were full-width
 * buttons). One component, four call sites.
 */
const props = defineProps({
  matches: { type: Array, default: () => [] },
  /** League band above the group. Omitted in My Club view, which is one team. */
  sectionLabel: { type: String, default: '' },
  sectionClass: { type: String, default: 'bg-brand-600' },
  /** Resolved by the parent, which holds the auth store and the teams list. */
  canEdit: { type: Function, default: () => false },
  isAdmin: { type: Boolean, default: false },
  /** Mark the viewer's own team's matches with a left edge. */
  highlightTeamId: { type: [Number, String], default: null },
});

const emit = defineEmits(['view', 'edit']);

const groups = computed(() => groupMatchesByDate(props.matches));

// The day header parks under the league header when there is one, and at the
// top of the viewport when there is not. 2.25rem is the league band's height.
const dayHeaderTop = computed(() => (props.sectionLabel ? '2.25rem' : '0px'));

const isHighlighted = match => {
  if (props.highlightTeamId == null || props.highlightTeamId === '')
    return false;
  const id = Number(props.highlightTeamId);
  return match.home_team_id === id || match.away_team_id === id;
};

const sheetMatch = ref(null);
const openSheet = match => {
  sheetMatch.value = match;
};
const closeSheet = () => {
  sheetMatch.value = null;
};

const onSheetView = match => {
  closeSheet();
  emit('view', match);
};

const onSheetEdit = match => {
  closeSheet();
  emit('edit', match);
};
</script>
