<template>
  <li
    class="match-row bg-card border border-line rounded-lg px-3 py-2.5 cursor-pointer hover:border-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
    :class="{ 'border-l-[3px] border-l-accent-400': highlight }"
    data-testid="match-list-row"
    :data-match-id="match.id"
    tabindex="0"
    role="button"
    :aria-label="ariaLabel"
    v-on="pressHandlers"
    @click="onClick"
    @keydown.enter.prevent="$emit('view', match)"
    @keydown.space.prevent="$emit('view', match)"
  >
    <!-- One line per team, each with its own score. Stacking is what makes
         full club names legible at 400px, and it removes the "is that
         away-home or home-away?" question the single-line score raised: each
         number sits against the team that scored it. Away over home, matching
         the "Away @ Home" ordering used everywhere else in MT. -->
    <div
      v-for="side in sides"
      :key="side.key"
      class="flex items-center gap-2 min-w-0"
      :data-testid="`match-row-${side.key}`"
    >
      <ClubLogo :logo-url="side.logoUrl" :name="side.name" size="xs" />
      <span
        class="flex-1 min-w-0 truncate text-sm leading-5"
        :class="side.winner ? 'font-bold text-fg' : 'font-medium text-fg'"
        >{{ side.name }}</span
      >

      <svg
        v-for="n in side.redCards"
        :key="`${side.key}-rc-${n}`"
        width="9"
        height="13"
        viewBox="0 0 24 24"
        class="shrink-0"
        :data-testid="`match-row-${side.key}-red-card`"
      >
        <title>Red card</title>
        <rect x="4" width="16" height="24" rx="2" fill="#EA3323" />
      </svg>

      <!-- The winner's tick, as today. The loser's cross is gone: bold plus a
           higher number already says which way it went, and a glyph on every
           row twice over is exactly the chrome this list is shedding. -->
      <span
        v-if="side.marker"
        class="shrink-0 text-xs"
        :class="side.markerClass"
        :aria-hidden="true"
        >{{ side.marker }}</span
      >

      <span
        class="shrink-0 w-6 text-right text-sm tabular-nums"
        :class="side.winner ? 'font-bold text-fg' : 'font-semibold text-fg'"
        :data-testid="`match-row-${side.key}-score`"
        >{{ side.score }}</span
      >
    </div>

    <!-- Meta line. Absent entirely for a finished match with nothing left to
         say, which is most of the archive — that is where the vertical space
         comes back. -->
    <div
      v-if="showMeta"
      class="flex items-center gap-2 mt-0.5 min-w-0"
      data-testid="match-row-meta"
    >
      <span
        v-if="kickoffLabel"
        class="text-xs font-medium text-fg-muted tabular-nums"
        data-testid="match-row-kickoff"
        >{{ kickoffLabel }}</span
      >
      <MatchStatusLabel
        v-else-if="showStatus"
        :status="match.match_status"
        :scoring-mode="match.scoring_mode"
        :match-date="match.match_date"
      />

      <span
        v-if="match.age_group_name"
        class="px-1.5 py-0.5 rounded bg-surface-alt text-[10px] font-semibold text-fg-muted shrink-0"
        data-testid="row-age-group"
        >{{ match.age_group_name }}</span
      >

      <!-- Which competition, on every row (SB-1105). The section band above
           says the division, and Flex is a child league of Homegrown — so the
           band says HOMEGROWN for a Flex fixture and a League one alike. This
           is the only thing on screen that tells them apart. -->
      <span
        v-if="competition"
        class="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide shrink-0"
        :class="competition.class"
        data-testid="row-competition"
        >{{ competition.label }}</span
      >

      <span class="flex-1" />

      <!-- Long press is undiscoverable on its own, and unreachable by keyboard
           or switch control at all. This button is the same sheet by another
           door: visible, tabbable, and named. -->
      <button
        v-if="hasSheet"
        type="button"
        class="shrink-0 -my-1 px-2 py-1 rounded text-fg-muted hover:text-fg hover:bg-surface-alt text-base leading-none"
        :aria-label="`More options for ${ariaLabel}`"
        data-testid="match-row-more"
        @click.stop="$emit('more', match)"
        @pointerdown.stop
        @keydown.enter.stop
        @keydown.space.stop
      >
        ⋯
      </button>
    </div>
  </li>
</template>

<script setup>
import { computed } from 'vue';
import ClubLogo from '../shared/ClubLogo.vue';
import MatchStatusLabel from '../ui/MatchStatusLabel.vue';
import { useLongPress } from '../../composables/useLongPress';
import { isMissingResult } from '../../utils/tournamentStatus';
import { competitionChip } from '../../utils/competitions';

/**
 * One match, compactly (SB-1101).
 *
 * The card this replaces spent most of its height on Type (which repeated the
 * section header), Status (which repeated the score), Match ID and Source
 * (admin forensics), and two full-width buttons. Three matches fitted on a
 * phone. Those four fields moved into a sheet behind a long press, the buttons
 * became the row itself, and the date moved up into a sticky day header.
 */
const props = defineProps({
  match: { type: Object, required: true },
  /** Whether this viewer may edit THIS match — resolved by the parent. */
  canEdit: { type: Boolean, default: false },
  /** Admin-only forensics (Match ID, Source) exist in the sheet. */
  isAdmin: { type: Boolean, default: false },
  /** Draw a left edge on the viewer's own team's matches. */
  highlight: { type: Boolean, default: false },
});

const emit = defineEmits(['view', 'more']);

/** Statuses under which a scoreline is real. Mirrors ScorePill's SCORABLE. */
const SCORED = ['completed', 'live', 'in_progress', 'forfeit'];

const hasScore = computed(
  () =>
    SCORED.includes(props.match.match_status) &&
    props.match.home_score != null &&
    props.match.away_score != null
);

const redCardsFor = teamId =>
  (props.match.red_cards ?? []).filter(c => c.team_id === teamId).length;

/**
 * Away first, then home. A team with neither more nor fewer goals than the
 * other is not a winner, so a draw marks both sides with `=` rather than
 * bolding either.
 */
const sides = computed(() => {
  const m = props.match;
  const drawn = hasScore.value && m.home_score === m.away_score;

  const build = (key, name, club, teamId, score, opponentScore) => {
    const won = hasScore.value && score > opponentScore;
    return {
      key,
      name: name || 'TBD',
      logoUrl: club?.logo_url || '',
      redCards: redCardsFor(teamId),
      // Absent is not zero: an unscored match shows an em dash, never a 0
      // that would claim nobody scored.
      score: hasScore.value ? score : '—',
      winner: won,
      marker: won ? '✓' : drawn ? '=' : '',
      markerClass: won ? 'text-green-600 dark:text-green-400' : 'text-fg-muted',
    };
  };

  return [
    build(
      'away',
      m.away_team_name,
      m.away_team_club,
      m.away_team_id,
      m.away_score,
      m.home_score
    ),
    build(
      'home',
      m.home_team_name,
      m.home_team_club,
      m.home_team_id,
      m.home_score,
      m.away_score
    ),
  ];
});

const missingResult = computed(() => isMissingResult(props.match));

/**
 * A fixture still to come says when, not "Scheduled" — the word adds nothing
 * next to a date header that already says which day. A fixture whose day has
 * passed with no result says "Not reported" instead (MatchStatusLabel), which
 * is the state `mt coverage` exists to find and the one a kickoff time would
 * misrepresent as still upcoming.
 */
const kickoffLabel = computed(() => {
  if (missingResult.value) return '';
  if (!['scheduled', 'tbd'].includes(props.match.match_status)) return '';
  const iso = props.match.scheduled_kickoff;
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
});

/**
 * A finished match needs no status: the scoreline and the tick already say so.
 * Everything else does — a forfeit's score looks ordinary, and postponed,
 * cancelled, live and unreported are not readable from the numbers at all.
 */
const showStatus = computed(() => props.match.match_status !== 'completed');

const hasSheet = computed(() => props.canEdit || props.isAdmin);

const competition = computed(() => competitionChip(props.match));

const showMeta = computed(
  () =>
    Boolean(kickoffLabel.value) ||
    showStatus.value ||
    Boolean(props.match.age_group_name) ||
    Boolean(competition.value) ||
    hasSheet.value
);

const ariaLabel = computed(() => {
  const m = props.match;
  const fixture = `${m.away_team_name || 'TBD'} at ${m.home_team_name || 'TBD'}`;
  if (hasScore.value) return `${fixture}, ${m.away_score} to ${m.home_score}`;
  return fixture;
});

const { handlers: pressHandlers, guardClick } = useLongPress(() => {
  if (hasSheet.value) emit('more', props.match);
});

const onClick = guardClick(() => emit('view', props.match));
</script>

<style scoped>
/*
 * A long press on a row must not also select its text or raise iOS's callout
 * menu — both fire before our timer does and leave the reader with a selection
 * they did not ask for on top of the sheet.
 */
.match-row {
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  /*
   * The row still scrolls vertically; only the double-tap-to-zoom delay and
   * horizontal panning are given up, so a press registers as a press.
   */
  touch-action: pan-y;
}
</style>
