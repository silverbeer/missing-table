<template>
  <tr
    :class="[
      { 'bg-surface-alt': striped },
      motw ? 'motw-row' : '',
      'cursor-pointer hover:bg-brand-50 dark:hover:bg-brand-500/10',
    ]"
    data-testid="match-table-row"
    :data-match-id="match.id"
    @click="$emit('view', match)"
  >
    <td v-if="mode === 'myclub'" class="border-b text-right text-fg-muted">
      {{ index + 1 }}
    </td>

    <!-- Sun 6 / Sep. The weekday is what a parent is looking for; the ISO
         date it replaces was not something anyone reads off a fixture list. -->
    <td class="border-b text-center leading-tight py-2">
      <template v-if="date">
        <div class="font-semibold text-fg tabular-nums">{{ date.day }}</div>
        <div class="text-[11px] uppercase tracking-wide text-fg-muted">
          {{ date.month }}
        </div>
      </template>
      <span v-else class="text-fg-muted">—</span>
    </td>

    <td class="border-b text-center text-sm text-fg-muted tabular-nums">
      {{ kickoff || '—' }}
    </td>

    <td class="border-b text-left px-2">
      <div class="flex items-center flex-wrap gap-x-2 gap-y-1">
        <!-- All Matches names both clubs; My Club names the opponent, since
             one of the two is always the team you are looking at. -->
        <span v-if="teams.mode === 'all'" class="flex items-center gap-1">
          <ClubLogo
            :logo-url="teams.away.logoUrl"
            :name="teams.away.name"
            size="xs"
          />
          <span :class="{ 'font-bold': teams.away.bold }">{{
            teams.away.name
          }}</span>
          <span v-if="teams.away.icon" :class="teams.away.iconClass">{{
            teams.away.icon
          }}</span>
          <span class="mx-0.5 text-fg-muted">@</span>
          <ClubLogo
            :logo-url="teams.home.logoUrl"
            :name="teams.home.name"
            size="xs"
          />
          <span :class="{ 'font-bold': teams.home.bold }">{{
            teams.home.name
          }}</span>
          <span v-if="teams.home.icon" :class="teams.home.iconClass">{{
            teams.home.icon
          }}</span>
        </span>

        <span v-else class="flex items-center gap-1">
          <span class="text-xs font-semibold uppercase text-fg-muted">{{
            teams.prefix
          }}</span>
          <ClubLogo
            :logo-url="teams.opponent.logoUrl"
            :name="teams.opponent.name"
            size="xs"
          />
          <span>{{ teams.opponent.name }}</span>
        </span>

        <!-- Which competition, on the row itself (SB-1121). The list is
             chronological and interleaves League with Flex, so no row can
             depend on a heading above it to say what it is. Same chip the
             phone row draws, from the same function (SB-1105). -->
        <span
          v-if="competition"
          class="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide"
          :class="competition.class"
          data-testid="row-competition"
          >{{ competition.label }}</span
        >
      </div>
    </td>

    <!-- The score is the point of the row, so it is the loudest thing in it.
         "Not played" and "No score" are different states and say so. -->
    <td class="border-b text-center">
      <span
        :class="[
          'tabular-nums',
          score.kind === 'score'
            ? 'text-base font-bold text-fg'
            : 'text-xs text-fg-muted',
        ]"
        data-testid="row-score"
        >{{ score.text }}</span
      >
    </td>

    <td v-if="mode === 'myclub'" class="border-b text-center">
      <span
        v-if="result && result !== '-'"
        class="px-2 py-1 rounded-full text-sm font-bold"
        :class="{
          'bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300':
            result === 'W',
          'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300':
            result === 'T',
          'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300':
            result === 'L',
        }"
        data-testid="row-result"
        >{{ result }}</span
      >
      <span v-else class="text-fg-muted">—</span>
    </td>

    <td class="border-b text-center">
      <span
        :class="{
          'px-2 py-1 rounded text-xs font-medium': true,
          'bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300':
            match.match_status === 'completed',
          'bg-brand-100 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200':
            match.match_status === 'scheduled',
          'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300':
            match.match_status === 'postponed',
          'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300':
            match.match_status === 'cancelled',
          'bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300':
            match.match_status === 'forfeit',
          'bg-red-600 text-white font-extrabold text-sm px-4 py-2 animate-pulse shadow-lg whitespace-nowrap':
            status.live,
          'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200 font-semibold whitespace-nowrap':
            status.inProgress && !status.live,
          'bg-surface-alt text-fg': !match.match_status,
        }"
        >{{ status.label }}</span
      >
    </td>

    <!-- No Match ID or Source column (SB-1121). They answer one question — am
         I about to overwrite a scraped score? — which is only ever asked
         inside Edit Match, and Edit Match has carried them all along. -->
    <td
      v-if="isAuthenticated"
      class="border-b text-center space-x-2"
      @click.stop
    >
      <button
        class="text-brand-600 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200 text-sm font-medium"
        @click="$emit('view', match)"
      >
        View
      </button>
      <button
        v-if="isAdmin"
        :data-testid="`motw-toggle-${match.id}`"
        :title="motw ? 'Remove as Match of the Week' : 'Make Match of the Week'"
        :aria-pressed="motw"
        :class="[
          'text-sm font-medium',
          motw
            ? 'text-accent-600 dark:text-accent-400'
            : 'text-fg-muted hover:text-accent-600 dark:hover:text-accent-400',
        ]"
        @click="$emit('toggle-motw', match)"
      >
        ◆
      </button>
      <button
        v-if="canEdit"
        class="text-brand-600 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200 text-sm font-medium"
        @click="$emit('edit', match)"
      >
        Edit
      </button>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue';
import ClubLogo from '../shared/ClubLogo.vue';
import { competitionChip } from '../../utils/competitions';
import { formatRowDate, scoreCell } from '../../utils/matchRow';

/**
 * One row of the desktop match table (SB-1121).
 *
 * This replaced four near-identical blocks of markup in MatchesView — three
 * All Matches sections plus My Club — which is how the two sub-tabs came to
 * be two visual languages for the same data. One component, four call sites,
 * and "the same look and feel" stops being something anyone has to remember.
 *
 * Presentational: the parent already computes the team display, the status
 * label and the result, and holds the auth store, so those arrive as props.
 */
const props = defineProps({
  match: { type: Object, required: true },
  /** 'all' names both clubs; 'myclub' names the opponent and shows a result. */
  mode: { type: String, default: 'myclub' },
  index: { type: Number, default: 0 },
  striped: { type: Boolean, default: false },
  /** From the parent's getMatchTeams(match). */
  teams: { type: Object, required: true },
  /** { label, live, inProgress } from the parent's status helpers. */
  status: {
    type: Object,
    default: () => ({ label: '', live: false, inProgress: false }),
  },
  /** 'W' | 'L' | 'T' | '-' from the parent, My Club only. */
  result: { type: String, default: '' },
  /** Local kickoff time, already formatted. */
  kickoff: { type: String, default: '' },
  canEdit: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },
  isAuthenticated: { type: Boolean, default: false },
  motw: { type: Boolean, default: false },
});

defineEmits(['view', 'edit', 'toggle-motw']);

const date = computed(() => formatRowDate(props.match.match_date));
const score = computed(() => scoreCell(props.match, props.mode));
const competition = computed(() => competitionChip(props.match));
</script>
