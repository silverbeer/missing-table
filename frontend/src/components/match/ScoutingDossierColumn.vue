<template>
  <!--
    One side of the Scouting tab (SB-1782): a team inside its own tables.
    Fest teams come from different conferences, so nothing here compares the
    two columns: each standing names its own conference. Degrades per field;
    absent renders as "—" or says so, never as 0.
  -->
  <section
    class="rounded-lg border border-line bg-card p-3 min-w-0"
    :data-testid="`scouting-${role}`"
  >
    <div
      v-if="!dossier || dossier.error"
      class="py-6 text-center text-sm text-fg-muted"
      data-testid="scouting-side-error"
    >
      <p class="font-medium text-fg">{{ teamName }}</p>
      <p>This team's scouting report is unavailable right now.</p>
    </div>

    <template v-else>
      <!-- Header -->
      <header class="flex items-center gap-2 mb-2">
        <ClubLogo
          :logo-url="dossier.team?.logo_url || ''"
          :name="dossier.team?.club_name || teamName"
          size="sm"
        />
        <h3
          class="flex-1 min-w-0 truncate text-sm font-semibold text-fg"
          data-testid="scouting-team-name"
        >
          {{ dossier.team?.name || teamName }}
        </h3>
        <span
          v-if="dossier.team?.pro_academy"
          class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide bg-accent-100 text-accent-700 dark:bg-accent-900/50 dark:text-accent-300"
          data-testid="scouting-pro-academy"
          >PRO ACADEMY</span
        >
      </header>

      <!-- Labels -->
      <div
        v-if="labels.length"
        class="flex flex-wrap gap-1 mb-2"
        data-testid="scouting-labels"
      >
        <span
          v-for="label in labels"
          :key="label"
          class="rounded px-1.5 py-0.5 text-[11px] bg-surface-alt text-fg-muted"
          data-testid="scouting-label"
          >{{ label }}</span
        >
      </div>

      <!-- Honest empty states -->
      <div
        v-if="noResults || noConference"
        class="rounded border border-dashed border-line px-3 py-3 mb-2 text-center"
        data-testid="scouting-side-empty"
      >
        <p v-if="noResults" class="text-xs font-semibold text-fg">
          No results tracked this season
        </p>
        <p v-if="noConference" class="text-xs text-fg-muted">
          Not registered in a conference at {{ ageName }}
        </p>
      </div>

      <!-- Standings, one line per conference -->
      <ul
        v-if="dossier.conferences?.length"
        class="space-y-1.5 mb-3"
        data-testid="scouting-conferences"
      >
        <li
          v-for="line in dossier.conferences"
          :key="line.division.id"
          class="text-xs"
          :data-testid="`scouting-conference-${line.kind}`"
        >
          <div class="flex items-baseline gap-1 min-w-0">
            <span class="shrink-0 font-semibold text-fg">{{
              kindLabel(line)
            }}</span>
            <span class="truncate text-fg-muted">{{ line.division.name }}</span>
          </div>
          <div
            v-if="line.no_results"
            class="text-fg-muted"
            data-testid="scouting-line-empty"
          >
            No results yet
          </div>
          <div
            v-else
            class="flex flex-wrap gap-x-2 tabular-nums text-fg"
            data-testid="scouting-line-stats"
          >
            <span data-testid="scouting-position">{{ position(line) }}</span>
            <span
              >{{ fmt(line.wins) }}-{{ fmt(line.draws) }}-{{
                fmt(line.losses)
              }}</span
            >
            <span class="text-fg-muted"
              >GF {{ perGame(line.gf_per_game) }} · GA
              {{ perGame(line.ga_per_game) }} per game</span
            >
          </div>
        </li>
      </ul>

      <!-- Key wins -->
      <div v-if="dossier.key_wins?.length" class="mb-3">
        <h4
          class="text-[11px] font-semibold uppercase tracking-wide text-fg-muted mb-1"
        >
          Key wins
        </h4>
        <ul class="space-y-1">
          <li
            v-for="win in dossier.key_wins.slice(0, 3)"
            :key="win.match_id"
            class="flex flex-wrap items-center gap-1 text-xs text-fg"
            data-testid="scouting-key-win"
          >
            <span class="font-mono font-semibold">{{ win.score }}</span>
            <span class="truncate">v {{ win.opponent.name }}</span>
            <span
              v-if="win.kind === 'pro_academy_upset'"
              class="rounded px-1 text-[10px] bg-accent-100 text-accent-700 dark:bg-accent-900/50 dark:text-accent-300"
              data-testid="scouting-upset"
              >Pro academy upset</span
            >
            <span v-if="win.opponent_position != null" class="text-fg-muted"
              >({{ ordinal(win.opponent_position) }} of
              {{ fmt(win.opponent_table_size) }} in
              {{ win.opponent_conference }})</span
            >
          </li>
        </ul>
      </div>

      <!-- Last 5 -->
      <div v-if="dossier.form?.length" class="mb-3">
        <h4
          class="text-[11px] font-semibold uppercase tracking-wide text-fg-muted mb-1"
        >
          Last {{ dossier.form.length }}
        </h4>
        <div class="flex gap-1" data-testid="scouting-form">
          <span
            v-for="f in dossier.form"
            :key="f.match_id"
            :title="`${f.score} v ${f.opponent.name}`"
            :class="[
              'w-5 h-5 rounded-sm text-[11px] font-bold flex items-center justify-center',
              resultClass(f.result),
            ]"
            data-testid="scouting-form-result"
            >{{ f.result }}</span
          >
        </div>
      </div>

      <!-- Stat-board badges -->
      <div v-if="side.badges?.length" data-testid="scouting-badges">
        <ul class="space-y-1">
          <li
            v-for="badge in side.badges"
            :key="badge.fact_id"
            class="text-xs text-fg"
            data-testid="scouting-badge"
          >
            {{ badgeText(badge) }}
          </li>
        </ul>
        <p
          v-if="side.badges_note"
          class="mt-1 text-[11px] text-fg-muted"
          data-testid="scouting-badges-note"
        >
          {{ side.badges_note }}
        </p>
      </div>
      <p
        v-else-if="side.badges == null && !noResults"
        class="text-[11px] text-fg-muted"
        data-testid="scouting-badges-unavailable"
      >
        Stat boards are unavailable right now.
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import ClubLogo from '../shared/ClubLogo.vue';

const props = defineProps({
  /** One MatchupSide from GET /api/matches/{id}/matchup. */
  side: { type: Object, required: true },
  /** Fallback name when the dossier could not be built. */
  teamName: { type: String, default: '' },
  /** "home" or "away": names the test id only. */
  role: { type: String, default: 'home' },
});

// Absent is "—", never 0: a team nobody measured has no value.
const fmt = v => (v == null ? '—' : v);
const perGame = v => (v == null ? '—' : Number(v).toFixed(1));

const ordinal = n => {
  const mod100 = n % 100;
  const suffix =
    mod100 >= 11 && mod100 <= 13
      ? 'th'
      : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th';
  return `${n}${suffix}`;
};

const dossier = computed(() => props.side?.dossier || null);
const flags = computed(() => dossier.value?.flags || []);
const noResults = computed(() => flags.value.includes('no_results'));
const noConference = computed(() => flags.value.includes('no_conference'));
const ageName = computed(() => dossier.value?.age_group?.name || 'this age');

const labels = computed(() => {
  const out = [];
  const context = dossier.value?.context;
  if (flags.value.includes('playing_up')) {
    const from = context?.season_age_group?.name;
    let label = from ? `Playing up from ${from}` : 'Playing up';
    if (flags.value.includes('playing_up_inferred')) label += ' (inferred)';
    out.push(label);
  }
  if (flags.value.includes('playing_down')) out.push('Older age group');
  if (flags.value.includes('low_sample')) out.push('Small sample');
  return out;
});

const KIND_LABELS = { flex: 'Flex', pathway: 'Pro Player Pathway' };
const kindLabel = line =>
  KIND_LABELS[line.kind] || line.league || line.competition || 'League';

const position = line =>
  line.position == null
    ? '—'
    : `${ordinal(line.position)} of ${fmt(line.table_size)}`;

const resultClass = r => {
  if (r === 'W') return 'bg-green-600 text-white';
  if (r === 'L') return 'bg-red-600 text-white';
  return 'bg-surface-alt text-fg-muted';
};

// "2nd in U15 Homegrown goals for per game, of 134 teams": a stat board, not a ranking.
// The title keeps its case but for the first letter ("W=3" stays "W=3").
const badgeText = b => {
  const title = b.title.charAt(0).toLowerCase() + b.title.slice(1);
  const teams = b.of === 1 ? 'team' : 'teams';
  return `${ordinal(b.rank)} in ${b.age_group} ${b.league} ${title}, of ${b.of} ${teams}`;
};
</script>
