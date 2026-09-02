<template>
  <SearchSelect
    ref="searchSelectRef"
    :model-value="modelValue"
    :options="options"
    :get-option-id="c => c.id"
    :get-option-label="c => c.name"
    :resolve-label="resolveLabel"
    :resolve-option="resolveOption"
    :placeholder="placeholder"
    :required="required"
    testid-prefix="club-combobox"
    @update:model-value="emit('update:modelValue', $event)"
    @update:query="query = $event"
  />
</template>

<script setup>
import { computed, ref } from 'vue';
import SearchSelect from './SearchSelect.vue';

/**
 * Club picker with type-ahead (SB-964).
 *
 * Thin wrapper over SearchSelect: no create-row, just case-insensitive
 * filtering on club name with a capped option list — matching the Add Match
 * combobox pattern instead of the bare native <select> this replaces on
 * Matches → My Club (which also meant no dark-mode theming, see SB-940).
 */
const props = defineProps({
  modelValue: { type: Number, default: null },
  clubs: { type: Array, default: () => [] },
  required: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Search clubs…' },
  maxOptions: { type: Number, default: 8 },
});

const emit = defineEmits(['update:modelValue']);

const query = ref('');
const searchSelectRef = ref(null);

const options = computed(() => {
  const q = query.value.trim().toLowerCase();
  const pool = q
    ? props.clubs.filter(c => (c.name || '').toLowerCase().includes(q))
    : props.clubs;
  return pool.slice(0, props.maxOptions);
});

// A pre-selected club (fan/manager landing on their own club, SB-599) can
// sit outside the first `maxOptions` once a club list grows past the cap, so
// SearchSelect can't always find it in the (capped) `options` array above to
// resolve a label from. This looks it up in the full, unfiltered `clubs`
// list instead — see SearchSelect's `resolveLabel` doc comment for why this
// is kept separate from `options` rather than folded into it.
const resolveLabel = id => props.clubs.find(c => c.id === id)?.name;

// Same edge case, but for the "✓ selected" confirmation line: SearchSelect's
// own `selectedOption` looks the id up in the capped `options` array, which
// this pre-selected club can likewise sort past (SB-964 regression — the
// checkmark line was vanishing even though the input above it, resolved via
// `resolveLabel`, still showed the right name).
const resolveOption = id => props.clubs.find(c => c.id === id) ?? null;

defineExpose({ focus: () => searchSelectRef.value?.focus() });
</script>
