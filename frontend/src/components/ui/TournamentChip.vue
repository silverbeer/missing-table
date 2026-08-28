<template>
  <span
    :class="[
      'inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium whitespace-nowrap',
      variantClasses,
    ]"
    data-testid="tournament-chip"
    :data-variant="variant"
  >
    <slot />
  </span>
</template>

<script setup>
import { computed } from 'vue';

/**
 * One chip, three meanings (SB-886).
 *
 * These used to be three unrelated hardcoded palettes inlined across
 * TournamentMatchCenter — `bg-indigo-100` for age, `bg-purple-100` for round,
 * `bg-brand-100` for the header's age group — none of which had a dark
 * variant, so they rendered as pale blocks on a navy card in dark mode.
 *
 * Each variant now pairs a light and a dark treatment, and the palettes stay
 * distinct so the three still read as different *kinds* of fact rather than
 * collapsing into one indistinguishable grey.
 */
const props = defineProps({
  variant: {
    type: String,
    default: 'group',
    validator: v => ['age', 'round', 'group'].includes(v),
  },
});

const VARIANTS = {
  // Age group — the tournament's primary axis, so it carries the brand navy.
  age: 'bg-brand-100 text-brand-700 dark:bg-brand-800 dark:text-brand-100',
  // Knockout round — progression, distinct from age at a glance.
  round:
    'bg-accent-100 text-accent-700 dark:bg-accent-800 dark:text-accent-100',
  // Pool / bracket group — the quietest of the three; neutral by design.
  group: 'bg-surface-alt text-fg-muted',
};

const variantClasses = computed(
  () => VARIANTS[props.variant] ?? VARIANTS.group
);
</script>
