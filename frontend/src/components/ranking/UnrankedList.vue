<template>
  <!--
    Teams under the minimum matches (SB-1785), listed once below the boards
    rather than on every board. Not ranked, so no rank column.
  -->
  <section
    class="min-w-0 rounded-lg border border-line bg-surface-alt/40 p-4"
    data-testid="unranked-list"
  >
    <h3 class="text-sm font-semibold text-fg mb-2" data-testid="unranked-title">
      Too few matches (under {{ minGp }}) — not ranked · {{ count }} teams
    </h3>
    <ul class="divide-y divide-line">
      <li
        v-for="row in rows"
        :key="row.team.id"
        class="flex items-center gap-2 py-1.5 text-sm"
        data-testid="unranked-row"
      >
        <span class="flex-1 min-w-0 truncate text-fg">{{ row.team.name }}</span>
        <span
          v-if="row.no_conference"
          class="shrink-0 rounded px-1.5 text-xs bg-surface-alt text-fg-muted"
          >No Homegrown conference</span
        >
        <span v-else class="shrink-0 truncate text-xs text-fg-muted">{{
          row.conference || '—'
        }}</span>
        <span
          class="shrink-0 w-12 text-right text-xs tabular-nums text-fg-muted"
          >{{ row.gp }} MP</span
        >
      </li>
    </ul>
    <p
      v-if="count > rows.length"
      class="mt-2 text-xs text-fg-muted"
      data-testid="unranked-more"
    >
      +{{ count - rows.length }} more
    </p>
  </section>
</template>

<script setup>
defineProps({
  rows: { type: Array, default: () => [] },
  count: { type: Number, default: 0 },
  minGp: { type: Number, default: 6 },
});
</script>
