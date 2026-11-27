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
        class="py-1.5 text-sm"
        data-testid="unranked-row"
      >
        <!-- Name gets the full width; conference and MP go underneath so a
             chip never squeezes the name on a phone (SB-1796). -->
        <span class="line-clamp-2 break-words leading-snug text-fg">{{
          row.team.name
        }}</span>
        <span class="block text-xs text-fg-muted">
          <span
            v-if="row.no_conference"
            class="inline-block rounded px-1.5 bg-surface-alt text-fg-muted"
            >No Homegrown conference</span
          >
          <span v-else>{{ row.conference || '—' }}</span>
          <span class="tabular-nums"> · {{ row.gp }} MP</span>
        </span>
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
