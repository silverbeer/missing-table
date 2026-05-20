<template>
  <div>
    <!-- No matches -->
    <div
      v-if="bracketTeams.length === 0"
      class="text-center py-10 text-gray-500"
    >
      No group-stage matches in this bracket yet.
    </div>

    <template v-else>
      <!-- Standings table -->
      <div
        class="overflow-x-auto bg-white rounded-lg border border-gray-200 mb-6"
      >
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-gray-600">
            <tr>
              <th class="px-2 py-2 w-8 text-center font-semibold">#</th>
              <th class="px-3 py-2 text-left font-semibold">Team</th>
              <th
                v-for="col in STAT_COLS"
                :key="col.key"
                class="px-2 py-2 text-center font-semibold w-12"
              >
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in standings"
              :key="row.team.id"
              :class="[
                idx === 0 ? 'bg-brand-50/50' : 'hover:bg-gray-50',
                'border-t border-gray-100',
              ]"
            >
              <td class="px-2 py-2 text-center text-gray-500 tabular-nums">
                {{ idx + 1 }}
              </td>
              <td
                :class="[
                  'px-3 py-2 truncate',
                  idx === 0 ? 'font-semibold text-gray-900' : 'text-gray-800',
                ]"
              >
                {{ row.team.name }}
              </td>
              <td
                v-for="col in STAT_COLS"
                :key="col.key"
                :class="[
                  'px-2 py-2 text-center tabular-nums',
                  col.key === 'pts'
                    ? 'font-bold text-gray-900'
                    : 'text-gray-700',
                ]"
              >
                {{ formatStat(row, col.key) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Head-to-head cross-table -->
      <div>
        <h3
          class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2"
        >
          Head-to-head
        </h3>
        <div class="overflow-x-auto bg-white rounded-lg border border-gray-200">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 text-gray-600">
              <tr>
                <th
                  class="px-3 py-2 text-left font-semibold sticky left-0 bg-gray-50 z-10"
                  style="min-width: 180px"
                ></th>
                <th
                  v-for="team in bracketTeams"
                  :key="`hdr-${team.id}`"
                  class="px-3 py-2 text-center font-semibold"
                  style="min-width: 110px"
                >
                  {{ team.name }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="rowTeam in bracketTeams"
                :key="`row-${rowTeam.id}`"
                class="border-t border-gray-100"
              >
                <td
                  class="px-3 py-2 font-medium text-gray-800 sticky left-0 bg-white z-10"
                >
                  {{ rowTeam.name }}
                </td>
                <td
                  v-for="colTeam in bracketTeams"
                  :key="`cell-${rowTeam.id}-${colTeam.id}`"
                  :class="[
                    'px-3 py-2 text-center tabular-nums',
                    rowTeam.id === colTeam.id
                      ? 'bg-gray-100 text-gray-300'
                      : 'text-gray-700',
                  ]"
                >
                  <span v-if="rowTeam.id === colTeam.id">—</span>
                  <span v-else>{{ h2hCell(rowTeam.id, colTeam.id) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  // Pre-filtered: only matches we want to include in the standings
  // (age group + tournament_group + group_stage round, filter happens
  // upstream so this component stays small and pure).
  matches: { type: Array, required: true },
});

// Columns shown in the standings table, in order.
const STAT_COLS = [
  { key: 'mp', label: 'MP' },
  { key: 'w', label: 'W' },
  { key: 'd', label: 'D' },
  { key: 'l', label: 'L' },
  { key: 'gf', label: 'GF' },
  { key: 'ga', label: 'GA' },
  { key: 'gd', label: 'GD' },
  { key: 'pts', label: 'PTS' },
];

// Unique teams that appear in this match set, sorted by name. Used as
// both the row and column axis of the head-to-head cross-table.
const bracketTeams = computed(() => {
  const seen = new Map();
  for (const m of props.matches) {
    if (m.home_team && !seen.has(m.home_team.id)) {
      seen.set(m.home_team.id, m.home_team);
    }
    if (m.away_team && !seen.has(m.away_team.id)) {
      seen.set(m.away_team.id, m.away_team);
    }
  }
  return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
});

// One completed match (or null) keyed by `${rowId}_${colId}` so the
// cross-table can look it up in O(1) per cell. The row team is the
// "perspective" team — the cell shows the score from the row team's
// point of view (i.e. row-team-goals first).
const completedByPair = computed(() => {
  const map = new Map();
  for (const m of props.matches) {
    if (m.match_status !== 'completed') continue;
    if (m.home_score == null || m.away_score == null) continue;
    map.set(`${m.home_team.id}_${m.away_team.id}`, m);
  }
  return map;
});

// Format a cross-table cell from the row team's perspective.
function h2hCell(rowId, colId) {
  const homeMatch = completedByPair.value.get(`${rowId}_${colId}`);
  if (homeMatch) {
    return formatScore(homeMatch.home_score, homeMatch.away_score, homeMatch);
  }
  const awayMatch = completedByPair.value.get(`${colId}_${rowId}`);
  if (awayMatch) {
    return formatScore(awayMatch.away_score, awayMatch.home_score, awayMatch);
  }
  return '-';
}

function formatScore(forGoals, againstGoals, match) {
  // Penalty-shootout suffix when present.
  if (
    match.home_penalty_score != null &&
    match.away_penalty_score != null &&
    forGoals === againstGoals
  ) {
    const isHomePerspective = match.home_score === forGoals;
    const pkFor = isHomePerspective
      ? match.home_penalty_score
      : match.away_penalty_score;
    const pkAgainst = isHomePerspective
      ? match.away_penalty_score
      : match.home_penalty_score;
    return `${forGoals}-${againstGoals} (${pkFor}-${pkAgainst} PK)`;
  }
  return `${forGoals}-${againstGoals}`;
}

// Per-team standings rows. PK shootout wins count as wins; PK goals are
// excluded from GF/GA (regulation only).
const standings = computed(() => {
  const rows = new Map();
  for (const team of bracketTeams.value) {
    rows.set(team.id, {
      team,
      mp: 0,
      w: 0,
      d: 0,
      l: 0,
      gf: 0,
      ga: 0,
      gd: 0,
      pts: 0,
    });
  }

  for (const m of props.matches) {
    if (m.match_status !== 'completed') continue;
    if (m.home_score == null || m.away_score == null) continue;

    const home = rows.get(m.home_team?.id);
    const away = rows.get(m.away_team?.id);
    if (!home || !away) continue;

    home.mp += 1;
    away.mp += 1;
    home.gf += m.home_score;
    home.ga += m.away_score;
    away.gf += m.away_score;
    away.ga += m.home_score;

    let homeWin = m.home_score > m.away_score;
    let awayWin = m.away_score > m.home_score;
    if (
      !homeWin &&
      !awayWin &&
      m.home_penalty_score != null &&
      m.away_penalty_score != null
    ) {
      homeWin = m.home_penalty_score > m.away_penalty_score;
      awayWin = m.away_penalty_score > m.home_penalty_score;
    }

    if (homeWin) {
      home.w += 1;
      home.pts += 3;
      away.l += 1;
    } else if (awayWin) {
      away.w += 1;
      away.pts += 3;
      home.l += 1;
    } else {
      home.d += 1;
      away.d += 1;
      home.pts += 1;
      away.pts += 1;
    }
  }

  for (const r of rows.values()) {
    r.gd = r.gf - r.ga;
  }

  return [...rows.values()].sort((a, b) => {
    if (b.pts !== a.pts) return b.pts - a.pts;
    if (b.gd !== a.gd) return b.gd - a.gd;
    if (b.gf !== a.gf) return b.gf - a.gf;
    return a.team.name.localeCompare(b.team.name);
  });
});

function formatStat(row, key) {
  if (key === 'gd') {
    return row.gd > 0 ? `+${row.gd}` : String(row.gd);
  }
  return row[key];
}
</script>
