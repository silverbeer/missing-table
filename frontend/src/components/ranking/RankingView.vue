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
