<template>
  <!-- Filters for a large tournament (SB-1749). One labelled select per
       filter, laid out in a wrapping row, so another one (Conference) is one
       more block here and nothing else moves. -->
  <div
    class="mb-4 flex flex-wrap items-end gap-3"
    data-testid="tournament-filters"
  >
    <div v-if="ageGroups.length > 0">
      <label
        for="tournament-age-group"
        class="block text-xs font-semibold text-fg-muted uppercase tracking-wider mb-1"
        >Age Group</label
      >
      <select
        id="tournament-age-group"
        :value="selectedAgeGroupId"
        :disabled="disabled"
        data-testid="tournament-age-group-select"
        class="block w-full sm:w-44 px-3 py-2 border border-line bg-card text-fg rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
        @change="onAgeGroupChange"
      >
        <option v-for="ag in ageGroups" :key="ag.id" :value="ag.id">
          {{ optionLabel(ag.name, ag.matches) }}
        </option>
      </select>
    </div>

    <!-- Hidden when this age has no groups ([]) and when the groups are not
         known (null). Neither case renders an empty control or a zero. -->
    <div v-if="hasGroups">
      <label
        for="tournament-group"
        class="block text-xs font-semibold text-fg-muted uppercase tracking-wider mb-1"
        >Group</label
      >
      <select
        id="tournament-group"
        :value="selectedGroup ?? ''"
        :disabled="disabled"
        data-testid="tournament-group-select"
        class="block w-full sm:w-44 px-3 py-2 border border-line bg-card text-fg rounded-md shadow-sm focus:outline-none focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
        @change="onGroupChange"
      >
        <option value="">All groups</option>
        <option v-for="g in groups" :key="g.key" :value="g.key">
          {{ optionLabel(g.key, g.matches) }}
        </option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  // [{ id, name, matches }] — `matches` null means not counted.
  ageGroups: { type: Array, default: () => [] },
  selectedAgeGroupId: { type: Number, default: null },
  // [{ key, division, label, matches }]. [] = this age has no groups;
  // null = unknown. Both hide the control.
  groups: { type: Array, default: null },
  selectedGroup: { type: String, default: null },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(['update:ageGroup', 'update:group']);

const hasGroups = computed(
  () => Array.isArray(props.groups) && props.groups.length > 0
);

// A count is shown only when there is one: a missing count is not "(0)".
const optionLabel = (name, matches) =>
  typeof matches === 'number' ? `${name} (${matches})` : name;

const onAgeGroupChange = event => {
  const id = Number(event.target.value);
  if (Number.isFinite(id)) emit('update:ageGroup', id);
};

const onGroupChange = event => {
  emit('update:group', event.target.value || null);
};
</script>
