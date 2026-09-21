<template>
  <ModalOverlay
    align="end"
    max-width="max-w-md"
    :label="`Options for ${fixture}`"
    close-label="Close options"
    @close="$emit('close')"
  >
    <div class="p-4" data-testid="match-actions-sheet">
      <!-- Which match this is about. A sheet raised by a press has no visible
           tie back to the row underneath it, so it restates the fixture. -->
      <p class="text-sm font-semibold text-fg pr-10">{{ fixture }}</p>
      <p class="text-xs text-fg-muted mt-0.5">{{ subtitle }}</p>

      <div class="mt-4 space-y-1">
        <button
          type="button"
          class="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium text-fg hover:bg-surface-alt"
          data-testid="sheet-view-match"
          @click="$emit('view', match)"
        >
          View match
        </button>
        <button
          v-if="canEdit"
          type="button"
          class="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium text-fg hover:bg-surface-alt"
          data-testid="sheet-edit-match"
          @click="$emit('edit', match)"
        >
          Edit match
        </button>
      </div>

      <!-- Forensics. Off the row because they answer "where did this record
           come from", which is an admin's question about the data, not a
           reader's question about the match. -->
      <dl
        v-if="isAdmin"
        class="mt-4 pt-3 border-t border-line grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 text-xs"
        data-testid="sheet-forensics"
      >
        <dt class="text-fg-muted">Competition</dt>
        <dd class="text-fg">{{ match.match_type_name || 'League' }}</dd>

        <dt class="text-fg-muted">Match ID</dt>
        <dd class="text-fg font-mono" data-testid="sheet-match-id">
          {{ match.match_id || '—' }}
        </dd>

        <dt class="text-fg-muted">Source</dt>
        <dd class="text-fg" data-testid="sheet-source">{{ sourceLabel }}</dd>

        <template v-if="match.updated_at">
          <dt class="text-fg-muted">Updated</dt>
          <dd class="text-fg">{{ updatedLabel }}</dd>
        </template>
      </dl>
    </div>
  </ModalOverlay>
</template>

<script setup>
import { computed } from 'vue';
import ModalOverlay from '../ui/ModalOverlay.vue';
import { formatDayHeading } from '../../utils/matchGrouping';

/**
 * Everything the compact match row stopped showing (SB-1101).
 *
 * Reached by long-pressing a row, or by the row's "⋯" button — the button
 * exists because a long press is invisible to a keyboard, a switch and a
 * screen reader, and undiscoverable even for a sighted user with a thumb.
 */
const props = defineProps({
  match: { type: Object, required: true },
  canEdit: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },
});

defineEmits(['close', 'view', 'edit']);

const fixture = computed(
  () =>
    `${props.match.away_team_name || 'TBD'} @ ${props.match.home_team_name || 'TBD'}`
);

const subtitle = computed(() => {
  const parts = [formatDayHeading(props.match.match_date)];
  if (props.match.age_group_name) parts.push(props.match.age_group_name);
  return parts.join(' · ');
});

const SOURCES = {
  manual: 'Manually entered',
  'match-scraper': 'Scraped from the official source',
  'match-scraper-agent': 'Scraped by the agent',
  'modular11-backfill': 'Backfilled from Modular11',
  import: 'Imported from backup',
};

/**
 * An unrecognised source shows the stored value rather than "Unknown source".
 * This row exists to answer "where did this record come from", and the raw
 * string answers it; the old wording hid it — and hid it for most of the
 * table, because `match-scraper-agent` and `modular11-backfill` were never in
 * this map.
 */
const sourceLabel = computed(() => {
  const source = props.match.source || 'manual';
  return SOURCES[source] || source;
});

const updatedLabel = computed(() => {
  const d = new Date(props.match.updated_at);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
});
</script>
