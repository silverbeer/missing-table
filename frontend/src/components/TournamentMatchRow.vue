<template>
  <div
    @click="$emit('select', match)"
    :class="[
      'bg-card rounded-lg border border-line border-l-[3px] px-3 sm:px-4 py-2.5 cursor-pointer',
      'hover:border-brand-300 hover:shadow-sm transition-all',
      mine
        ? 'border-l-accent-400 hover:border-l-accent-400'
        : 'border-l-transparent',
    ]"
    data-testid="tournament-match-row"
    :data-mine="mine ? 'true' : 'false'"
  >
    <!-- Mobile meta row: kickoff and chips ride above the fixture. -->
    <div class="flex items-center justify-between mb-1.5 sm:hidden">
      <div class="flex items-center gap-1.5 min-w-0 flex-wrap">
        <span class="font-mono text-xs font-semibold text-fg tabular-nums">
          {{ kickoffLabel || '—' }}
        </span>
        <TournamentChip
          v-for="chip in chips"
          :key="chip.key"
          :variant="chip.variant"
        >
          {{ chip.text }}
        </TournamentChip>
      </div>
      <MatchStatusLabel
        :status="match.match_status"
        :match-date="match.match_date"
        class="shrink-0 ml-2"
      />
    </div>

    <div class="flex items-center gap-2 sm:gap-3">
      <!-- Kickoff time is the row's anchor: it is what a parent at a
           tournament actually scans for. Tabular figures so the column of
           times lines up down the list. -->
      <div class="hidden sm:block w-[68px] shrink-0 leading-tight">
        <div class="font-mono text-[13px] font-semibold text-fg tabular-nums">
          {{ kickoffTime || '—' }}
        </div>
        <div
          v-if="kickoffMeridiem"
          class="font-mono text-[10px] text-fg-muted tracking-wide"
        >
          {{ kickoffMeridiem }}
        </div>
      </div>

      <div class="hidden sm:flex gap-1 shrink-0">
        <TournamentChip
          v-for="chip in chips"
          :key="chip.key"
          :variant="chip.variant"
        >
          {{ chip.text }}
        </TournamentChip>
      </div>

      <div class="flex-1 flex items-center gap-2 min-w-0">
        <div class="flex-1 flex items-center gap-1.5 min-w-0 justify-end">
          <span
            :class="[
              'text-sm text-right truncate min-w-0',
              isHomeMine ? 'font-semibold text-fg' : 'font-medium text-fg',
            ]"
            >{{ match.home_team?.name }}</span
          >
          <img
            v-if="match.home_team_club?.logo_url"
            :src="match.home_team_club.logo_url"
            alt=""
            class="w-5 h-5 object-contain shrink-0"
          />
        </div>

        <ScorePill
          :home-score="match.home_score"
          :away-score="match.away_score"
          :home-penalty-score="match.home_penalty_score"
          :away-penalty-score="match.away_penalty_score"
          :status="match.match_status"
        />

        <div class="flex-1 flex items-center gap-1.5 min-w-0">
          <img
            v-if="match.away_team_club?.logo_url"
            :src="match.away_team_club.logo_url"
            alt=""
            class="w-5 h-5 object-contain shrink-0"
          />
          <span
            :class="[
              'text-sm text-left truncate min-w-0',
              isAwayMine ? 'font-semibold text-fg' : 'font-medium text-fg',
            ]"
            >{{ match.away_team?.name }}</span
          >
        </div>
      </div>

      <!-- Status only. The whole row is already clickable, so the old
           "Preview" pseudo-link here read as a fourth match state. -->
      <div
        class="hidden sm:flex items-center gap-1.5 w-[86px] shrink-0 justify-end"
      >
        <MatchStatusLabel
          :status="match.match_status"
          :match-date="match.match_date"
        />
        <span aria-hidden="true" class="text-fg-muted text-sm leading-none"
          >›</span
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import ScorePill from './ui/ScorePill.vue';
import TournamentChip from './ui/TournamentChip.vue';
import MatchStatusLabel from './ui/MatchStatusLabel.vue';
import { ROUND_LABELS_SHORT as ROUND_LABELS } from '../utils/tournamentRounds';
import { isMyMatch } from '../utils/tournamentStatus';

const props = defineProps({
  match: { type: Object, required: true },
  // Age-group chip is noise on a single-age tournament — the header already
  // states the age group.
  showAgeChip: { type: Boolean, default: false },
  // Knockout rows show which round they are; group-stage rows show the pool.
  showRoundChip: { type: Boolean, default: false },
  showGroupChip: { type: Boolean, default: true },
  // The signed-in user's club / team, so their own fixtures stand out.
  // Both null (signed out) makes the highlight a silent no-op.
  myClubId: { type: Number, default: null },
  myTeamId: { type: Number, default: null },
});

defineEmits(['select']);

const identity = computed(() => ({
  clubId: props.myClubId,
  teamId: props.myTeamId,
}));

const mine = computed(() => isMyMatch(props.match, identity.value));

const isHomeMine = computed(
  () =>
    mine.value &&
    ((props.myClubId != null &&
      props.match.home_team_club?.id === props.myClubId) ||
      (props.myTeamId != null && props.match.home_team?.id === props.myTeamId))
);

const isAwayMine = computed(
  () =>
    mine.value &&
    ((props.myClubId != null &&
      props.match.away_team_club?.id === props.myClubId) ||
      (props.myTeamId != null && props.match.away_team?.id === props.myTeamId))
);

// Kickoff split into time and meridiem so the meridiem can sit under the time
// as a caption and keep the numerals aligned in their own column.
const kickoffParts = computed(() => {
  const iso = props.match.scheduled_kickoff;
  if (!iso) return { time: '', meridiem: '' };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { time: '', meridiem: '' };
  const time = d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
  const [clock, meridiem = ''] = time.split(' ');
  return { time: clock, meridiem };
});

const kickoffTime = computed(() => kickoffParts.value.time);
const kickoffMeridiem = computed(() => kickoffParts.value.meridiem);
const kickoffLabel = computed(() =>
  kickoffParts.value.time
    ? `${kickoffParts.value.time} ${kickoffParts.value.meridiem}`.trim()
    : ''
);

const chips = computed(() => {
  const out = [];
  if (props.showAgeChip && props.match.age_group) {
    out.push({ key: 'age', variant: 'age', text: props.match.age_group.name });
  }
  if (props.showRoundChip) {
    const label = ROUND_LABELS[props.match.tournament_round];
    if (label) out.push({ key: 'round', variant: 'round', text: label });
  }
  if (props.showGroupChip && props.match.tournament_group) {
    out.push({
      key: 'group',
      variant: 'group',
      text: props.match.tournament_group,
    });
  }
  return out;
});
</script>
