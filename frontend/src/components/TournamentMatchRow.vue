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
        :scoring-mode="match.scoring_mode"
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

        <div
          v-if="editing"
          class="flex items-center gap-1 shrink-0"
          @click.stop
          data-testid="tournament-score-editor"
        >
          <input
            v-model="homeScore"
            type="number"
            min="0"
            inputmode="numeric"
            aria-label="Home score"
            data-testid="edit-home-score"
            class="w-10 h-8 text-center text-sm font-semibold rounded border border-line bg-surface text-fg tabular-nums"
            @keyup.enter="submit"
            @keyup.esc="cancel"
          />
          <span class="text-fg-muted text-xs">-</span>
          <input
            v-model="awayScore"
            type="number"
            min="0"
            inputmode="numeric"
            aria-label="Away score"
            data-testid="edit-away-score"
            class="w-10 h-8 text-center text-sm font-semibold rounded border border-line bg-surface text-fg tabular-nums"
            @keyup.enter="submit"
            @keyup.esc="cancel"
          />
        </div>
        <ScorePill
          v-else
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
        v-if="!editing"
        class="hidden sm:flex items-center gap-1.5 w-[86px] shrink-0 justify-end"
      >
        <MatchStatusLabel
          :status="match.match_status"
          :scoring-mode="match.scoring_mode"
          :match-date="match.match_date"
        />
        <button
          v-if="canEdit"
          type="button"
          class="text-fg-muted hover:text-brand-500 text-sm leading-none px-1"
          :aria-label="`Edit score: ${match.home_team?.name} vs ${match.away_team?.name}`"
          data-testid="edit-score-button"
          @click.stop="startEditing"
        >
          ✎
        </button>
        <span
          v-else
          aria-hidden="true"
          class="text-fg-muted text-sm leading-none"
          >›</span
        >
      </div>

      <div
        v-else
        class="flex items-center gap-1 shrink-0 justify-end"
        @click.stop
      >
        <button
          type="button"
          class="px-2 h-8 rounded text-xs font-semibold bg-brand-500 text-white disabled:opacity-50"
          data-testid="save-score-button"
          :disabled="saving || !canSubmit"
          @click.stop="submit"
        >
          {{ saving ? '…' : 'Save' }}
        </button>
        <button
          type="button"
          class="px-2 h-8 rounded text-xs font-medium text-fg-muted hover:text-fg"
          data-testid="cancel-score-button"
          :disabled="saving"
          @click.stop="cancel"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Shootouts exist only because regulation ended level, so the inputs
         only exist then — and only in a bracket round, where a draw has to be
         broken. -->
    <div
      v-if="editing && showPenalties"
      class="flex items-center justify-center gap-1.5 mt-2"
      data-testid="penalty-editor"
      @click.stop
    >
      <span class="text-[11px] uppercase tracking-wide text-fg-muted"
        >Penalties</span
      >
      <input
        v-model="homePenaltyScore"
        type="number"
        min="0"
        inputmode="numeric"
        aria-label="Home penalty score"
        data-testid="edit-home-penalty"
        class="w-10 h-7 text-center text-xs rounded border border-line bg-surface text-fg tabular-nums"
      />
      <span class="text-fg-muted text-xs">-</span>
      <input
        v-model="awayPenaltyScore"
        type="number"
        min="0"
        inputmode="numeric"
        aria-label="Away penalty score"
        data-testid="edit-away-penalty"
        class="w-10 h-7 text-center text-xs rounded border border-line bg-surface text-fg tabular-nums"
      />
    </div>

    <p
      v-if="editing && saveError"
      class="mt-1.5 text-xs text-danger-500 text-center"
      role="alert"
      data-testid="save-score-error"
    >
      {{ saveError }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
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
  // Whether this viewer may score THIS match. Resolved by the parent, which
  // already holds the auth store, so the row stays a presentation component.
  canEdit: { type: Boolean, default: false },
  // Set by the parent while its PATCH is in flight, and to the API's message
  // if that write fails. A failure keeps the editor open with the typed
  // scores intact — retyping a score you already entered is the worst thing
  // this row could ask of someone standing on a touchline.
  saving: { type: Boolean, default: false },
  saveError: { type: String, default: '' },
});

const emit = defineEmits(['select', 'save']);

// Bracket rounds are the only ones where a level score has to be broken, so
// they are the only ones that show shootout inputs. Mirrors the rule in
// AdminTournaments.vue.
const BRACKET_ROUNDS = new Set([
  'round_of_32',
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'third_place',
  'final',
]);

const editing = ref(false);
const homeScore = ref('');
const awayScore = ref('');
const homePenaltyScore = ref('');
const awayPenaltyScore = ref('');

// Absent is not zero: a match nobody has scored opens with empty boxes, not
// with 0-0, which would be a claim that it finished goalless.
const asField = value => (value == null ? '' : String(value));

const startEditing = () => {
  homeScore.value = asField(props.match.home_score);
  awayScore.value = asField(props.match.away_score);
  homePenaltyScore.value = asField(props.match.home_penalty_score);
  awayPenaltyScore.value = asField(props.match.away_penalty_score);
  editing.value = true;
};

const cancel = () => {
  editing.value = false;
};

const toScore = value => {
  if (value === '' || value == null) return null;
  const n = Number(value);
  return Number.isInteger(n) && n >= 0 ? n : null;
};

const parsedHome = computed(() => toScore(homeScore.value));
const parsedAway = computed(() => toScore(awayScore.value));

// Both sides or neither — a half-entered score is not a result.
const canSubmit = computed(
  () => parsedHome.value !== null && parsedAway.value !== null
);

const showPenalties = computed(
  () =>
    BRACKET_ROUNDS.has(props.match.tournament_round) &&
    canSubmit.value &&
    parsedHome.value === parsedAway.value
);

const submit = () => {
  if (!canSubmit.value || props.saving) return;
  const payload = {
    match: props.match,
    home_score: parsedHome.value,
    away_score: parsedAway.value,
  };
  if (showPenalties.value) {
    const homePens = toScore(homePenaltyScore.value);
    const awayPens = toScore(awayPenaltyScore.value);
    if (homePens !== null && awayPens !== null) {
      payload.home_penalty_score = homePens;
      payload.away_penalty_score = awayPens;
    }
  }
  emit('save', payload);
};

// The parent owns the write, so the editor closes on the transition out of
// `saving` — but only when the write actually succeeded.
watch(
  () => props.saving,
  (isSaving, wasSaving) => {
    if (wasSaving && !isSaving && !props.saveError) editing.value = false;
  }
);

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
