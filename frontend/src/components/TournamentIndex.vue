<template>
  <div data-testid="tournament-index">
    <!-- A link to a tournament this viewer cannot see, or one that is gone.
         Says no more than that: never whether it exists. -->
    <p
      v-if="notice"
      class="mb-4 rounded-md border border-line bg-card px-4 py-3 text-sm text-fg-muted"
      role="status"
      data-testid="tournament-index-notice"
    >
      {{ notice }}
    </p>

    <ul class="grid grid-cols-1 sm:grid-cols-2 gap-3" role="list">
      <li v-for="card in cards" :key="card.tournament.id">
        <button
          type="button"
          :class="[
            'w-full h-full text-left bg-card rounded-xl border p-4 flex items-start gap-3 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-0',
            card.state === 'live'
              ? 'border-red-400 ring-1 ring-red-400 dark:border-red-500 dark:ring-red-500 hover:border-red-500'
              : 'border-line hover:border-brand-400',
          ]"
          data-testid="tournament-card"
          :data-state="card.state"
          :data-id="card.tournament.id"
          @click="$emit('open', card.tournament.id)"
        >
          <img
            v-if="card.tournament.logo_url"
            :src="card.tournament.logo_url"
            alt=""
            class="w-12 h-12 object-contain shrink-0"
            data-testid="tournament-card-logo"
          />
          <!-- No logo: a neutral mark, the same size, so the names line up. -->
          <span
            v-else
            class="w-12 h-12 rounded-lg border border-line bg-surface-alt text-fg-muted shrink-0 flex items-center justify-center"
            aria-hidden="true"
            data-testid="tournament-logo-placeholder"
          >
            <svg
              viewBox="0 0 24 24"
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z" />
              <path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3" />
            </svg>
          </span>

          <span class="min-w-0 flex-1">
            <span class="flex items-start justify-between gap-2">
              <span
                class="min-w-0 break-words font-semibold text-fg leading-tight"
                data-testid="tournament-card-name"
                >{{ card.tournament.name }}</span
              >
              <!-- Status in words as well as colour. No dates, no chip:
                   unknown is not a state. -->
              <span
                v-if="card.chip"
                :class="[
                  'inline-flex items-center gap-1.5 shrink-0 px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wide',
                  card.chipClass,
                ]"
                data-testid="tournament-card-status"
              >
                <span
                  v-if="card.state === 'live'"
                  class="w-1.5 h-1.5 rounded-full bg-red-500"
                  aria-hidden="true"
                ></span>
                {{ card.chip }}
              </span>
            </span>
            <span
              class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-fg-muted"
            >
              <span v-if="card.dates" data-testid="tournament-card-dates">{{
                card.dates
              }}</span>
              <span
                v-if="card.dates && card.tournament.location"
                aria-hidden="true"
                >·</span
              >
              <span
                v-if="card.tournament.location"
                data-testid="tournament-card-location"
                >{{ card.tournament.location }}</span
              >
            </span>
            <!-- Only a count the server gave. A count it could not load is
                 absent, never "0 matches". -->
            <span
              v-if="card.matchCount != null"
              class="mt-1 block text-xs text-fg-muted tabular-nums"
              data-testid="tournament-card-count"
              >{{ card.matchCount }}
              {{ card.matchCount === 1 ? 'match' : 'matches' }}</span
            >
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import {
  formatTournamentDateRange,
  tournamentStatus,
} from '../utils/tournamentStatus';

const props = defineProps({
  // Already in status order (`compareByStatus`); rendered as given.
  tournaments: { type: Array, required: true },
  notice: { type: String, default: null },
  now: { type: Date, default: null },
});

defineEmits(['open']);

const CHIPS = {
  // The list carries no matches, so "live" here is the dates alone — the
  // tournament is on today, not necessarily mid-match. Same words as the hero
  // card's date-only state, and a static dot: a pulse would claim a match in
  // progress on a rest day.
  live: {
    label: 'Happening today',
    cls: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-100',
  },
  soon: {
    label: 'Upcoming',
    cls: 'bg-brand-100 text-brand-700 dark:bg-brand-800 dark:text-brand-100',
  },
  upcoming: {
    label: 'Upcoming',
    cls: 'bg-brand-100 text-brand-700 dark:bg-brand-800 dark:text-brand-100',
  },
  completed: {
    label: 'Completed',
    cls: 'bg-surface-alt text-fg-muted',
  },
};

// The list rows carry no matches, so status here is from the dates alone —
// the same rule the hero card applies to a paged tournament.
const cards = computed(() =>
  props.tournaments.map(t => {
    const status = tournamentStatus(t, [], props.now ?? new Date());
    const chip = status ? CHIPS[status.state] : null;
    return {
      tournament: t,
      state: status?.state ?? 'unknown',
      chip: chip?.label ?? null,
      chipClass: chip?.cls ?? '',
      dates: formatTournamentDateRange(t),
      matchCount: typeof t.match_count === 'number' ? t.match_count : null,
    };
  })
);
</script>
