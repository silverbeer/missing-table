<template>
  <!--
    One leaderboard (SB-1785). The coverage note leads every card, verbatim:
    a team's numbers are earned against its own conference, so the board
    compares stats across conferences rather than saying who is stronger.
  -->
  <section
    class="rounded-lg border border-line bg-card p-4 flex flex-col"
    :data-testid="`board-${board.key}`"
  >
    <h3 class="text-base font-semibold text-fg" data-testid="board-title">
      {{ board.title }}
    </h3>
    <div v-if="coverage" class="mt-1 mb-3 space-y-1">
      <p class="text-xs font-medium text-fg-muted" data-testid="board-coverage">
        {{ coverageLine }}
      </p>
      <p class="text-xs text-fg-muted" data-testid="board-coverage-note">
        {{ coverage.note }}
      </p>
    </div>

    <p
      v-if="!board.rows || board.rows.length === 0"
      class="py-6 text-center text-sm text-fg-muted"
      data-testid="board-no-rows"
    >
      No team qualifies yet
    </p>
    <ol v-else class="divide-y divide-line">
      <li v-for="(row, i) in board.rows" :key="row.team.id">
        <button
          type="button"
          class="w-full flex items-center gap-2 py-2 text-left hover:bg-surface-alt rounded focus:outline-none focus:bg-surface-alt"
          data-testid="board-row"
          @click="$emit('select-team', row)"
        >
          <span
            class="w-8 shrink-0 text-right text-sm tabular-nums text-fg-muted"
            data-testid="row-rank"
            >{{ rankLabel(i) }}</span
          >
          <ClubLogo
            :logo-url="row.club_logo_url || ''"
            :name="row.team.club_name || row.team.name"
            size="xs"
          />
          <span class="flex-1 min-w-0">
            <span
              class="block truncate text-sm font-medium text-brand-600 dark:text-brand-300"
              data-testid="row-team"
              >{{ row.team.name }}</span
            >
            <span class="block truncate text-xs text-fg-muted">
              <span
                v-if="
                  row.team.club_name && row.team.club_name !== row.team.name
                "
                data-testid="row-club"
                >{{ row.team.club_name }} ·
              </span>
              <span
                v-if="row.no_conference"
                class="inline-block rounded px-1.5 bg-surface-alt text-fg-muted"
                data-testid="row-no-conference"
                >No Homegrown conference</span
              >
              <span v-else data-testid="row-conference">{{
                row.conference || '—'
              }}</span>
            </span>
          </span>
          <span
            class="shrink-0 text-xs tabular-nums text-fg-muted"
            data-testid="row-gp"
            >{{ row.gp ?? '—' }} GP</span
          >
          <span
            class="shrink-0 min-w-[3.5rem] text-right text-sm font-semibold tabular-nums text-fg"
            data-testid="row-value"
            >{{ formatValue(row) }}</span
          >
        </button>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import ClubLogo from '../shared/ClubLogo.vue';

const props = defineProps({
  board: { type: Object, required: true },
  coverage: { type: Object, default: null },
  ageGroup: { type: String, default: '' },
  league: { type: String, default: '' },
});

defineEmits(['select-team']);

const plural = (n, word) => (n === 1 ? word : `${word}s`);

const coverageLine = computed(() => {
  const c = props.coverage;
  const teams = [c.teams, props.ageGroup, props.league, plural(c.teams, 'team')]
    .filter(p => p !== '' && p != null)
    .join(' ');
  const conferences = `${c.conferences} ${plural(c.conferences, 'conference')}`;
  return [teams, conferences, `min ${c.min_gp} GP`].join(' · ');
});

// The API ranks; ties share a rank (1, 1, 3). "T" marks a shared one.
const rankLabel = i => {
  const rows = props.board.rows;
  const rank = rows[i].rank;
  if (rank == null) return '—';
  const tied =
    (i > 0 && rows[i - 1].rank === rank) ||
    (i < rows.length - 1 && rows[i + 1].rank === rank);
  return tied ? `T${rank}` : String(rank);
};

// Absent is "—", never 0: a team nobody measured has no value.
const formatValue = row => {
  const v = row.value;
  switch (props.board.key) {
    case 'unbeaten':
      return row.w == null ? '—' : `${row.w}-${row.d}-${row.l}`;
    case 'pro_wins':
      return v == null || row.pro_games == null
        ? '—'
        : `${v} of ${row.pro_games}`;
    case 'gd_pg':
      if (v == null) return '—';
      return v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2);
    default:
      if (v == null) return '—';
      return props.board.variant === 'per_game' ? v.toFixed(2) : String(v);
  }
};
</script>
