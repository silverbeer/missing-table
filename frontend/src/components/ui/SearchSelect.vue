<template>
  <div class="relative" @keydown.escape.stop="close">
    <input
      ref="inputEl"
      v-model="query"
      type="text"
      role="combobox"
      aria-autocomplete="list"
      :aria-expanded="open"
      :aria-controls="listId"
      :placeholder="placeholder"
      :required="required && modelValue == null"
      :data-testid="`${testidPrefix}-input`"
      class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
      @focus="open = true"
      @input="onInput"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="choose(options[activeIndex])"
    />

    <!-- Confirmed selection, so the choice stays visible once the list
         closes and the input just shows text. -->
    <p
      v-if="selectedOption"
      class="text-xs text-emerald-600 dark:text-emerald-400 mt-1"
      :data-testid="`${testidPrefix}-selected`"
    >
      ✓
      <slot name="selected" :option="selectedOption">{{
        getOptionLabel(selectedOption)
      }}</slot>
    </p>

    <ul
      v-if="open && options.length"
      :id="listId"
      role="listbox"
      :data-testid="`${testidPrefix}-list`"
      class="absolute z-20 mt-1 w-full max-h-64 overflow-auto bg-card border border-line rounded-md shadow-lg"
    >
      <li
        v-for="(opt, i) in options"
        :key="getOptionId(opt)"
        role="option"
        :aria-selected="i === activeIndex"
        :data-testid="`${testidPrefix}-${getOptionTestId(opt)}`"
        class="px-3 py-2 cursor-pointer flex items-center justify-between gap-2"
        :class="
          i === activeIndex
            ? 'bg-brand-50 dark:bg-brand-500/15'
            : 'hover:bg-line/40'
        "
        @mousedown.prevent="choose(opt)"
        @mouseenter="activeIndex = i"
      >
        <slot name="option" :option="opt" :active="i === activeIndex">
          <span class="text-sm text-fg truncate">{{
            getOptionLabel(opt)
          }}</span>
        </slot>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

/**
 * Generic type-and-search combobox shell (SB-964).
 *
 * Owns the query text, open/closed state and keyboard navigation (arrows,
 * Enter, Escape). The parent supplies an already-filtered-and-capped
 * `options` array plus id/label accessors, so no team/club-specific
 * filtering logic lives here — TeamCombobox and ClubCombobox both wrap this
 * for their own domain rules (age-group filtering, create-on-no-match, club
 * name search, ...).
 */
const props = defineProps({
  // The selected option's id, or null when nothing is chosen.
  modelValue: { default: null },
  options: { type: Array, default: () => [] },
  getOptionId: { type: Function, default: o => o.id },
  getOptionLabel: { type: Function, default: o => o.name },
  // Lets a wrapping component (TeamCombobox) tell an option row's testid
  // apart from another kind of row it renders (its "create new" row) —
  // everything else just gets the shared "option" testid.
  getOptionTestId: { type: Function, default: () => 'option' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  // Builds this component's testids: `${testidPrefix}-input/-list/-option/-selected`.
  testidPrefix: { type: String, required: true },
  // Resolves the display label for `modelValue` independent of the (capped)
  // `options` array — e.g. a pre-selected club/team (SB-599 auto-select)
  // that sorts past the parent's maxOptions cap before any query is typed
  // (SB-964 known edge case). Falls back to searching `options` when this
  // returns nothing, which is what keeps late-arriving async `options`
  // resolving correctly. Deliberately *not* folded into the `options` prop
  // itself: that was tried first and it fed back into the label-resolution
  // watch below on every keystroke (since `options` also drives filtering),
  // occasionally clobbering the first character a user typed right after a
  // pre-selection.
  resolveLabel: { type: Function, default: null },
  // Same idea as `resolveLabel`, but returns the full option object rather
  // than just its label string, resolved against the parent's full
  // unfiltered list rather than the (possibly capped) `options` array. Used
  // for the "✓ selected" confirmation line below, whose slot may need more
  // than the label (TeamCombobox's league/tournament badge) — and, unlike
  // `options`, stays correct once the selected item sorts past maxOptions
  // (SB-964 regression). Falls back to searching `options` when this returns
  // nothing, same as `resolveLabel`.
  resolveOption: { type: Function, default: null },
});

const emit = defineEmits(['update:modelValue', 'update:query']);

const query = ref('');
const open = ref(false);
const activeIndex = ref(0);
const inputEl = ref(null);
const listId = `search-select-${Math.random().toString(36).slice(2, 9)}`;

// Mirrors resolveQueryFromModelValue below: prefer resolveOption (correct
// even when the selected item sorts past the parent's maxOptions cap), and
// fall back to searching the (possibly capped) `options` array. Keeping this
// in sync with the input's own label resolution is the point — before this,
// the confirmation line looked up `options` only, so it could vanish for a
// still-valid, still-displayed selection (SB-964 regression).
const selectedOption = computed(() => {
  if (props.modelValue == null) return null;
  const resolved = props.resolveOption?.(props.modelValue);
  if (resolved != null) return resolved;
  return (
    props.options.find(o => props.getOptionId(o) === props.modelValue) ?? null
  );
});

watch(query, val => emit('update:query', val));

watch(
  () => props.options,
  opts => {
    if (activeIndex.value >= opts.length) activeIndex.value = 0;
  }
);

// Typing invalidates any prior choice — otherwise an edited query would
// submit against the option picked before the edit. This is also what makes
// clearing the input clear the selection.
const onInput = () => {
  open.value = true;
  activeIndex.value = 0;
  if (props.modelValue != null) emit('update:modelValue', null);
};

const move = delta => {
  if (!open.value) {
    open.value = true;
    return;
  }
  const n = props.options.length;
  if (!n) return;
  activeIndex.value = (activeIndex.value + delta + n) % n;
};

const choose = opt => {
  if (!opt) return;
  query.value = props.getOptionLabel(opt);
  open.value = false;
  emit('update:modelValue', props.getOptionId(opt));
};

const close = () => {
  open.value = false;
};

// Tracks the label this component itself last wrote into query.value (as
// opposed to whatever the user has since typed there) — see the guard on the
// options-change watch below, which needs to tell those two apart.
let lastResolvedLabel = query.value;

// Resolve the label for a modelValue set from outside (a pre-selected
// club/team on mount, or a later programmatic assignment): prefer
// `resolveLabel` (independent of the possibly-capped `options` array), and
// fall back to searching `options` when it finds nothing. Depends only on
// `modelValue`, not `options`, so it can't be re-triggered by every
// keystroke's filtering pass while the id it resolves against is unchanged.
const resolveQueryFromModelValue = id => {
  if (id == null) return;
  const label = props.resolveLabel?.(id);
  if (label != null) {
    query.value = label;
    lastResolvedLabel = label;
    return;
  }
  const found = props.options.find(o => props.getOptionId(o) === id);
  if (found) {
    query.value = props.getOptionLabel(found);
    lastResolvedLabel = query.value;
  }
};

watch(() => props.modelValue, resolveQueryFromModelValue, { immediate: true });

// Late-load / context-change path: `options` can change either because
// async data arrived after modelValue was already set (e.g. a team list
// fetched after mount) or because some context `resolveLabel` itself depends
// on shifted — e.g. TeamCombobox's labelFormatter reading a different
// age-group after the user changes filters (SB-964 regression: the label
// went stale because this used to bail out as soon as resolveLabel resolved
// *anything*, on the assumption a resolvable label meant nothing to do; but
// resolveLabel can resolve a *different*, newly-correct label for the same
// still-valid id, and that only gets written to query.value here).
//
// Re-resolve whenever query.value is still exactly what this component wrote
// there itself — i.e. nothing has touched the input since. If it isn't (the
// user has typed something, and modelValue/options haven't caught up to that
// yet), leave it alone: rewriting it here would clobber that keystroke and,
// worse, its own `query` watch above would re-emit the clobbered value
// upward, which can feed back into a wrapper's own filtering and cascade
// (the "does not disturb the cap once typing starts" scenario).
watch(
  () => props.options,
  () => {
    if (query.value !== lastResolvedLabel) return;
    resolveQueryFromModelValue(props.modelValue);
  }
);

defineExpose({
  focus: () => inputEl.value?.focus(),
  // Lets a wrapping component (e.g. TeamCombobox) reproduce its own
  // "clear on parent reset" behavior without reaching into this component's
  // internals.
  clear: () => {
    query.value = '';
  },
  isOpen: () => open.value,
});
</script>
