<template>
  <!--
    SB-1800: a quiet way to learn that MT has live scoring. One small icon;
    tapping it reveals a line and a link to the Manager roles page. No claim
    or request action, by design: the goal is awareness, not inbound requests.
  -->
  <div class="relative" data-testid="live-scoring-hint">
    <button
      type="button"
      class="inline-flex items-center justify-center w-7 h-7 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500"
      :aria-expanded="open ? 'true' : 'false'"
      aria-controls="live-scoring-hint-panel"
      aria-label="About live scoring"
      data-testid="live-scoring-hint-toggle"
      @click="open = !open"
    >
      <!-- broadcast icon -->
      <svg
        viewBox="0 0 24 24"
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="2" />
        <path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49" />
        <path
          d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14"
        />
      </svg>
    </button>
    <div
      v-if="open"
      id="live-scoring-hint-panel"
      role="note"
      class="absolute left-0 bottom-full mb-2 w-64 max-w-[calc(100vw-2rem)] rounded-lg bg-slate-800 border border-slate-600 p-3 text-xs text-slate-200 shadow-lg z-20"
      data-testid="live-scoring-hint-panel"
    >
      <p>
        Team managers can live score matches in Missing Table: goals, halftime
        and full time, as they happen.
      </p>
      <button
        type="button"
        class="mt-2 text-xs font-medium text-sky-300 hover:text-sky-200 underline underline-offset-2"
        data-testid="live-scoring-hint-roles"
        @click="openRoles"
      >
        Learn about manager roles
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useManagerRolesPage } from '@/composables/useManagerRolesPage';

const open = ref(false);
const roles = useManagerRolesPage();
const openRoles = () => {
  open.value = false;
  roles.open();
};
</script>
