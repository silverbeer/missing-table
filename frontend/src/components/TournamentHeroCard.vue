<template>
  <div
    class="bg-card rounded-xl shadow-sm border border-line overflow-hidden mb-6"
    data-testid="tournament-hero"
  >
    <!-- Status ribbon: where this tournament is in its own life. Hidden
         entirely when the tournament has no parsable dates — unknown renders
         as absent, not as "upcoming". -->
    <div
      v-if="status"
      class="flex items-center gap-2 flex-wrap px-4 sm:px-5 py-2 bg-brand-600 text-white text-xs font-medium tracking-wide"
      data-testid="tournament-status-ribbon"
      :data-state="status.state"
    >
      <span
        class="w-1.5 h-1.5 rounded-full shrink-0"
        :class="
          status.state === 'live' ? 'bg-red-400 animate-pulse' : 'bg-accent-400'
        "
      ></span>
      <span class="uppercase">{{ status.label }}</span>
      <span v-if="stageLabel" class="opacity-60">·</span>
      <span v-if="stageLabel" class="uppercase opacity-90">{{
        stageLabel
      }}</span>
      <span
        v-if="countdown"
        class="ml-auto font-mono tabular-nums"
        data-testid="tournament-countdown"
        >{{ countdown }} to
        {{ status.state === 'live' ? 'next kickoff' : 'first kickoff' }}</span
      >
    </div>

    <div class="px-4 sm:px-5 pt-4 flex items-start gap-3 sm:gap-4 flex-wrap">
      <img
        v-if="tournament.logo_url"
        :src="tournament.logo_url"
        :alt="`${tournament.name} logo`"
        class="w-14 h-14 sm:w-16 sm:h-16 rounded-lg object-contain bg-card border border-line shrink-0"
        data-testid="tournament-logo"
      />
      <div class="min-w-0 flex-1">
        <h2 class="text-xl sm:text-2xl font-bold text-fg leading-tight">
          {{ tournament.name }}
        </h2>
        <div
          class="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-sm text-fg-muted"
        >
          <span v-if="dateRange">{{ dateRange }}</span>
          <span v-if="dateRange && tournament.location" aria-hidden="true"
            >·</span
          >
          <span v-if="tournament.location">{{ tournament.location }}</span>
          <template v-for="ag in tournament.age_groups || []" :key="ag.id">
            <span aria-hidden="true">·</span>
            <TournamentChip variant="age">{{ ag.name }}</TournamentChip>
          </template>
          <span aria-hidden="true">·</span>
          <span
            >{{ matchCount }} {{ matchCount === 1 ? 'match' : 'matches' }}</span
          >
          <template v-if="descriptionLink">
            <span aria-hidden="true">·</span>
            <a
              :href="descriptionLink.href"
              target="_blank"
              rel="noopener noreferrer"
              class="text-brand-600 dark:text-brand-300 hover:text-accent-600 dark:hover:text-accent-300 font-medium underline underline-offset-2"
              data-testid="tournament-schedule-link"
              @click.stop
              >{{ descriptionLink.label }} ↗</a
            >
          </template>
        </div>
        <p
          v-if="descriptionText"
          class="mt-2 text-sm text-fg-muted"
          data-testid="tournament-description"
        >
          {{ descriptionText }}
        </p>
      </div>

      <slot name="actions" />
    </div>

    <!-- Your next match. Absent for signed-out visitors and for a club with no
         fixtures here — the strip collapses rather than rendering an empty
         promise. -->
    <div
      v-if="nextMyMatch"
      class="mx-4 sm:mx-5 mt-4 rounded-lg border border-accent-400 bg-accent-50 dark:bg-accent-900/30 px-3 sm:px-4 py-2.5 flex items-center gap-3 flex-wrap cursor-pointer hover:border-accent-500 transition-colors"
      data-testid="tournament-next-match"
      @click="$emit('select-match', nextMyMatch)"
    >
      <span
        class="text-[10px] font-semibold uppercase tracking-widest text-accent-700 dark:text-accent-300 shrink-0"
        >Your next match</span
      >
      <span class="flex-1 min-w-[180px] text-sm font-semibold text-fg truncate">
        {{ nextMyMatch.home_team?.name }}
        <span class="font-normal text-fg-muted"
          >vs {{ nextMyMatch.away_team?.name }}</span
        >
      </span>
      <span
        class="font-mono text-xs font-semibold text-fg tabular-nums shrink-0"
      >
        {{ nextMyMatchWhen }}
      </span>
    </div>

    <!-- Quick stats. Every tile is a plain count of what is on this page, so
         none of them need a coverage denominator; the "played" tile is dimmed
         at zero because zero played is an honest count of a tournament that has
         not started, not a missing measurement. -->
    <div class="mt-4 border-t border-line flex flex-wrap">
      <div
        v-for="stat in stats"
        :key="stat.key"
        class="flex-1 min-w-[88px] px-4 sm:px-5 py-2.5 border-r border-line last:border-r-0"
        data-testid="tournament-stat"
      >
        <div
          :class="[
            'text-xl sm:text-2xl font-bold leading-none tabular-nums',
            stat.dim ? 'text-fg-muted' : 'text-fg',
          ]"
        >
          {{ stat.value }}
        </div>
        <div
          class="text-[10px] font-semibold uppercase tracking-widest text-fg-muted mt-1"
        >
          {{ stat.label }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import TournamentChip from './ui/TournamentChip.vue';
import {
  tournamentStatus,
  formatCountdown,
  isMyMatch,
  relativeDayLabel,
  SCORED_STATUSES,
} from '../utils/tournamentStatus';

const props = defineProps({
  tournament: { type: Object, required: true },
  matches: { type: Array, default: () => [] },
  myClubId: { type: Number, default: null },
  myTeamId: { type: Number, default: null },
  stageLabel: { type: String, default: null },
});

defineEmits(['select-match']);

// A ticking clock so "22h 14m" stays true without a page refresh. One interval
// for the whole card; cleared on unmount.
const now = ref(new Date());
let timer = null;
onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date();
  }, 30000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

const status = computed(() =>
  tournamentStatus(props.tournament, props.matches, now.value)
);

const countdown = computed(() => {
  const target = status.value?.countdownTo;
  if (!target) return null;
  return formatCountdown(new Date(target) - now.value);
});

const formatDate = value => {
  if (!value) return '';
  return new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString(
    'en-US',
    {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }
  );
};

const dateRange = computed(() => {
  const start = formatDate(props.tournament.start_date);
  if (!start) return '';
  const end = formatDate(props.tournament.end_date);
  return end && end !== start ? `${start} – ${end}` : start;
});

const matchCount = computed(() => props.matches.length);

// `tournaments.description` is frequently just the source schedule URL. Render
// it as a named link rather than as a 66-character string of body text.
const URL_RE = /^https?:\/\/\S+$/i;

const descriptionLink = computed(() => {
  const raw = (props.tournament.description || '').trim();
  if (!URL_RE.test(raw)) return null;
  let label = 'View schedule';
  try {
    const host = new URL(raw).hostname.replace(/^www\./, '');
    if (host.includes('gotsport')) label = 'Schedule on GotSport';
    else label = `Schedule on ${host}`;
  } catch {
    // Unparsable despite matching the shape — fall back to the generic label.
  }
  return { href: raw, label };
});

const descriptionText = computed(() => {
  const raw = (props.tournament.description || '').trim();
  return raw && !URL_RE.test(raw) ? raw : null;
});

const myMatches = computed(() =>
  props.matches.filter(m =>
    isMyMatch(m, { clubId: props.myClubId, teamId: props.myTeamId })
  )
);

const nextMyMatch = computed(() => {
  const upcoming = myMatches.value
    .filter(m => !SCORED_STATUSES.includes(m.match_status))
    .filter(m => m.match_status !== 'cancelled')
    .filter(
      m => !m.scheduled_kickoff || new Date(m.scheduled_kickoff) > now.value
    )
    .slice()
    .sort((a, b) =>
      (a.scheduled_kickoff || '') < (b.scheduled_kickoff || '') ? -1 : 1
    );
  return upcoming[0] ?? null;
});

const nextMyMatchWhen = computed(() => {
  const m = nextMyMatch.value;
  if (!m) return '';
  const day = relativeDayLabel(m.match_date, now.value);
  const dayLabel =
    day ??
    (m.match_date
      ? new Date(
          `${String(m.match_date).slice(0, 10)}T00:00:00`
        ).toLocaleDateString('en-US', { weekday: 'short' })
      : '');
  if (!m.scheduled_kickoff) return dayLabel;
  const time = new Date(m.scheduled_kickoff).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
  const away = formatCountdown(new Date(m.scheduled_kickoff) - now.value);
  return away ? `${dayLabel} ${time} · in ${away}` : `${dayLabel} ${time}`;
});

const stats = computed(() => {
  const played = props.matches.filter(m =>
    SCORED_STATUSES.includes(m.match_status)
  ).length;
  const days = new Set(
    props.matches
      .map(m => m.match_date)
      .filter(Boolean)
      .map(d => String(d).slice(0, 10))
  ).size;

  const out = [];
  // Only shown when the viewer actually has a club in this tournament —
  // otherwise the tile would read "0 your matches", which is a claim about a
  // club that isn't here.
  if (myMatches.value.length > 0) {
    out.push({
      key: 'mine',
      value: myMatches.value.length,
      label: 'Your matches',
    });
  }
  out.push({
    key: 'played',
    value: played,
    label: 'Played',
    dim: played === 0,
  });
  out.push({ key: 'total', value: props.matches.length, label: 'Matches' });
  if (days > 0)
    out.push({ key: 'days', value: days, label: days === 1 ? 'Day' : 'Days' });
  return out;
});
</script>
