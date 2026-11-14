<template>
  <!--
    Collapsible filter panel for the Table and Matches tabs (SB-1714), after
    the Android panel (SB-1680). Closed, the header is the summary of what is
    narrowing the list; open, the rows below say it.

    Open until the viewer first closes it, then remembered per tab — the
    filters are the first thing a new visitor needs and the last thing a
    returning one wants to scroll past.
  -->
  <section
    class="rounded-lg border border-line bg-surface-alt/40"
    :data-testid="testid"
  >
    <button
      type="button"
      class="w-full flex items-center gap-3 px-4 py-3 min-h-[44px] text-left"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-controls="bodyId"
      :data-testid="`${testid}-toggle`"
      @click="toggle"
    >
      <!-- sliders icon -->
      <svg
        class="w-5 h-5 shrink-0 text-fg-muted"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.5"
          d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75"
        />
      </svg>
      <span v-if="open || !summary" class="flex-1 text-sm font-semibold text-fg"
        >Filters</span
      >
      <span
        v-else
        class="flex-1 min-w-0 line-clamp-2 text-sm text-fg"
        :title="summary"
        :data-testid="`${testid}-summary`"
        >{{ summary }}</span
      >
      <span class="sr-only">{{ open ? 'Hide filters' : 'Show filters' }}</span>
      <svg
        :class="[
          'w-5 h-5 shrink-0 text-fg-muted transition-transform',
          open ? 'rotate-180' : '',
        ]"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </button>
    <div
      v-show="open"
      :id="bodyId"
      class="px-4 pb-4 pt-1 space-y-4"
      :data-testid="`${testid}-body`"
    >
      <slot />
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  /** Which tab's panel this is — the localStorage key and the test id. */
  view: { type: String, required: true },
  /** One line of what is narrowing the list; shown while closed. */
  summary: { type: String, default: '' },
});

const STORAGE_PREFIX = 'mt.filterPanel.v1.';
const storageKey = `${STORAGE_PREFIX}${props.view}`;
const testid = `filter-panel-${props.view}`;
const bodyId = `${testid}-body`;

// localStorage may throw (Safari private mode); a failure is "open".
const readOpen = () => {
  try {
    return window.localStorage.getItem(storageKey) !== 'closed';
  } catch {
    return true;
  }
};

const open = ref(readOpen());

const toggle = () => {
  open.value = !open.value;
  try {
    window.localStorage.setItem(storageKey, open.value ? 'open' : 'closed');
  } catch {
    // Remembering is a convenience; the toggle still works this visit.
  }
};
</script>
