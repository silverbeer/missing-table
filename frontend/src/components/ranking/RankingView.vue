<template>
  <!--
    The Ranking tab (SB-1785). Leaderboards first; Power Rating joins as a
    second sub-tab later. The sub-nav stays hidden while there is one entry.
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
      </button>
    </nav>
    <!-- SB-1803: announce the Power Rating (SB-1784) before it ships. Wording
         promises only what the approved design commits to; the Power Rating
         list replaces this note (SB-1809). -->
    <aside
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
  </div>
</template>

<script setup>
import { ref } from 'vue';
import LeaderboardsPanel from './LeaderboardsPanel.vue';

defineEmits(['navigate-to-team']);

const subTabs = [{ id: 'leaderboards', name: 'Leaderboards' }];
const activeSubTab = ref(subTabs[0].id);
</script>
