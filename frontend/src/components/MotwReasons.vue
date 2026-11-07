<template>
  <!--
    "Why this is the Match of the Week" (SB-1552, SB-1577). Shared by the hero
    and the match detail page so the two never disagree. null and [] render
    nothing — no heading over an empty list.
  -->
  <div v-if="show" class="motw-reasons" data-testid="motw-reasons">
    <h3 class="motw-reasons-title">{{ title }}</h3>
    <ul class="motw-reasons-list">
      <li
        v-for="(reason, i) in reasons"
        :key="i"
        class="motw-reason"
        data-testid="motw-reason"
        :data-kind="marker(reason.kind).value || 'none'"
      >
        <span
          class="motw-reason-mark"
          aria-hidden="true"
          data-testid="motw-reason-mark"
          >{{ marker(reason.kind).icon }}</span
        >
        <span>
          <span v-if="marker(reason.kind).label" class="sr-only"
            >{{ marker(reason.kind).label }}:
          </span>
          {{ reason.text }}
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { hasReasons, reasonMarker } from '@/utils/featuredReasons';

const props = defineProps({
  // [{text, kind}] or null.
  reasons: { type: Array, default: null },
  title: { type: String, default: 'Why this is the Match of the Week' },
});

const show = computed(() => hasReasons(props.reasons));
const marker = reasonMarker;
</script>

<style scoped>
.motw-reasons {
  max-width: 62ch;
}

.motw-reasons-title {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #b45309;
}

:global(.dark .motw-reasons-title) {
  color: #f59e0b;
}

.motw-reasons-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.motw-reason {
  display: flex;
  gap: 8px;
  font-size: 14px;
  line-height: 20px;
  color: rgb(var(--color-fg));
}

.motw-reason-mark {
  flex-shrink: 0;
  width: 1.25em;
  text-align: center;
  color: #f59e0b;
}
</style>
