<template>
  <!--
    The Ranking tab (SB-1785). Leaderboards first, then the Power Rating
    (SB-1809) for whoever canSeePowerRating allows. The sub-nav stays hidden
    while there is one entry.
  -->
  <div data-testid="ranking-view">
    <nav
      v-if="subTabs.length > 1"
      class="flex flex-wrap gap-2 mb-4"
      aria-label="Ranking views"
      data-testid="ranking-subnav"
    >
      <button
        v-for="tab in subTabs"
        :key="tab.id"
        type="button"
        @click="activeSubTab = tab.id"
        :class="[
          'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
          activeSubTab === tab.id
            ? 'bg-brand-500 text-white shadow-sm'
            : 'bg-surface-alt text-fg-muted hover:bg-line',
        ]"
      >
        {{ tab.name }}
        <span
          v-if="tab.preview"
          class="ml-1 inline-block rounded px-1.5 py-0.5 align-[1px] text-[10px] font-semibold uppercase tracking-wide bg-accent-100 text-accent-800 dark:bg-accent-900/40 dark:text-accent-200"
          data-testid="power-rating-preview-chip"
          >Preview</span
        >
      </button>
    </nav>
    <!-- SB-1803: announce the Power Rating (SB-1784) before it ships. Wording
         promises only what the approved design commits to. It stays until
         the Power Rating is public; the preview sub-tab does not need it. -->
    <aside
      v-if="activeSubTab !== 'power-rating'"
      class="mb-4 rounded-lg border border-line bg-card px-3 py-2 text-sm text-fg"
      data-testid="power-rating-coming-soon"
    >
      <p>
        <span
          class="mr-1.5 inline-block rounded px-1.5 py-0.5 align-[1px] text-[10px] font-semibold uppercase tracking-wide bg-accent-100 text-accent-800 dark:bg-accent-900/40 dark:text-accent-200"
          >Coming soon</span
        >
        <strong class="font-semibold">Power Rating.</strong>
        One rating for every Homegrown team from U15 to U19, built from results
        and opponent strength. It appears once MLS NEXT Fest results connect the
        conferences.
      </p>
    </aside>
    <LeaderboardsPanel
      v-if="activeSubTab === 'leaderboards'"
      @navigate-to-team="$emit('navigate-to-team', $event)"
    />
    <PowerRatingPanel
      v-else-if="activeSubTab === 'power-rating'"
      @navigate-to-team="$emit('navigate-to-team', $event)"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import LeaderboardsPanel from './LeaderboardsPanel.vue';
import PowerRatingPanel from './PowerRatingPanel.vue';

defineEmits(['navigate-to-team']);

// Launch gate (SB-1809): the Power Rating waits for the Fest backtest
// (SB-1806). Until then only admins see it, marked Preview. Launching is
// this one line: set it to true and every viewer of the Ranking tab gets the
// sub-tab, without the chip.
const POWER_RATING_PUBLIC = false;

const authStore = useAuthStore();
const canSeePowerRating = computed(
  () => POWER_RATING_PUBLIC || Boolean(authStore.isAdmin?.value)
);

const subTabs = computed(() => [
  { id: 'leaderboards', name: 'Leaderboards' },
  ...(canSeePowerRating.value
    ? [
        {
          id: 'power-rating',
          name: 'Power Rating',
          preview: !POWER_RATING_PUBLIC,
        },
      ]
    : []),
]);
const activeSubTab = ref('leaderboards');

// Signing out of admin mid-view must not leave a hidden panel on screen.
watch(subTabs, tabs => {
  if (!tabs.some(t => t.id === activeSubTab.value)) {
    activeSubTab.value = tabs[0].id;
  }
});
</script>
