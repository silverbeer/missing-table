<template>
  <div>
    <!-- No matches in this bracket -->
    <div v-if="!hasAnyR32" class="text-center py-10 text-gray-500">
      No matches in this bracket yet.
    </div>

    <div v-else class="overflow-x-auto pb-4">
      <div class="bracket-grid min-w-[1080px]">
        <!-- Column headers -->
        <div
          v-for="(round, i) in ROUNDS"
          :key="`hdr-${round.key}`"
          :class="['bracket-header', `col-${i + 1}`]"
        >
          {{ round.label }}
        </div>

        <!-- R32 cells (16) -->
        <div
          v-for="(m, idx) in r32Matches"
          :key="`r32-${idx}`"
          :class="['bracket-cell', `col-1`, `r32-${idx}`]"
        >
          <BracketCell :match="m" @click="$emit('match-click', m)" />
        </div>

        <!-- Later rounds: real matches where loaded, placeholder otherwise -->
        <div
          v-for="(m, idx) in r16Cells"
          :key="`r16-${idx}`"
          :class="['bracket-cell', `col-2`, `r16-${idx}`]"
        >
          <BracketCell :match="m" @click="$emit('match-click', m)" />
        </div>
        <div
          v-for="(m, idx) in qfCells"
          :key="`qf-${idx}`"
          :class="['bracket-cell', `col-3`, `qf-${idx}`]"
        >
          <BracketCell :match="m" @click="$emit('match-click', m)" />
        </div>
        <div
          v-for="(m, idx) in sfCells"
          :key="`sf-${idx}`"
          :class="['bracket-cell', `col-4`, `sf-${idx}`]"
        >
          <BracketCell :match="m" @click="$emit('match-click', m)" />
        </div>
        <div :class="['bracket-cell', `col-5`, `final-0`]">
          <BracketCell
            :match="finalCell"
            :is-final="true"
            @click="$emit('match-click', finalCell)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, h } from 'vue';

const props = defineProps({
  matches: { type: Array, required: true },
});

defineEmits(['match-click']);

const ROUNDS = [
  { key: 'round_of_32', label: 'Round of 32' },
  { key: 'round_of_16', label: 'Round of 16' },
  { key: 'quarterfinal', label: 'Quarterfinals' },
  { key: 'semifinal', label: 'Semifinals' },
  { key: 'final', label: 'Final' },
];

// `tournament_round_order` is the explicit bracket-position field (0-based,
// top of bracket = 0). When present, the match goes at that slot directly.
// When absent, the match is placed via the per-round fallback chain below:
//   R32: id-order
//   R16 / QF / SF / Final: feeder-derived (pair (2k, 2k+1) → slot k), then id-order
//
// The mlssoccer.com canonical layout doesn't always match the order matches
// were inserted into the DB, so id-order alone produces misaligned
// brackets — tournament_round_order is the proper fix.

// Place matches into a fixed-size slot array. Explicit tournament_round_order
// wins; collisions and unordered matches drop into `unresolved` for the
// caller's secondary placement strategy (feeder-derived or id-order).
function placeWithExplicitOrder(matches, slotCount) {
  const placed = Array.from({ length: slotCount }, () => null);
  const unresolved = [];
  for (const m of matches) {
    const slot = m.tournament_round_order;
    if (slot == null || slot < 0 || slot >= slotCount || placed[slot] != null) {
      unresolved.push(m);
      continue;
    }
    placed[slot] = m;
  }
  return { placed, unresolved };
}

// Drop unresolved matches into remaining empty slots in id order.
function fillRemainingByIdOrder(placed, unresolved, slotCount) {
  const remaining = [...unresolved].sort((a, b) => a.id - b.id);
  let cursor = 0;
  for (const m of remaining) {
    while (cursor < slotCount && placed[cursor] != null) cursor++;
    if (cursor >= slotCount) break;
    placed[cursor] = m;
  }
  return placed;
}

// R32 has no feeder round — only explicit-order and id-order placement.
const r32Matches = computed(() => {
  const matches = props.matches.filter(
    m => m.tournament_round === 'round_of_32'
  );
  const { placed, unresolved } = placeWithExplicitOrder(matches, 16);
  return fillRemainingByIdOrder(placed, unresolved, 16);
});

const hasAnyR32 = computed(() => r32Matches.value.some(m => m != null));

// ── Feeder-derived placement ──────────────────────────────────────────────
// For R16 / QF / SF / Final, we don't just sort by id — we place each match
// directly under its two feeder matches.
//
// In a single-elimination bracket, the pair (2k, 2k+1) of feeder slots feeds
// into slot k of the next round. So if team A advanced from R32 slot 4 and
// team B from R32 slot 5, the R16 match they meet in goes at R16 slot 2.
//
// We detect the feeder slot by looking up each team's id in the feeder
// round's placement. Matches whose teams aren't in the feeder round (e.g.
// placeholders before the feeder round is loaded, or off-bracket teams)
// fall back to id-order placement in whatever slots remain.

function buildFeederSlotByTeam(feederCells) {
  const map = new Map();
  feederCells.forEach((m, slot) => {
    if (!m) return;
    const homeId = m.home_team?.id;
    const awayId = m.away_team?.id;
    if (homeId != null) map.set(homeId, slot);
    if (awayId != null) map.set(awayId, slot);
  });
  return map;
}

function placeByFeeder(roundKey, feederCells, slotCount) {
  const matches = props.matches.filter(m => m.tournament_round === roundKey);

  // Pass 1: respect explicit tournament_round_order.
  const { placed, unresolved: needFeederOrId } = placeWithExplicitOrder(
    matches,
    slotCount
  );

  // Pass 2: for the remainder, derive slot from the two teams' feeder slots.
  const feederSlotByTeam = buildFeederSlotByTeam(feederCells);
  const stillUnresolved = [];
  for (const m of needFeederOrId) {
    const feederSlots = [];
    const homeSlot = feederSlotByTeam.get(m.home_team?.id);
    const awaySlot = feederSlotByTeam.get(m.away_team?.id);
    if (homeSlot != null) feederSlots.push(homeSlot);
    if (awaySlot != null) feederSlots.push(awaySlot);

    if (feederSlots.length === 0) {
      stillUnresolved.push(m);
      continue;
    }
    const targetSlot = Math.floor(Math.min(...feederSlots) / 2);
    if (
      targetSlot < 0 ||
      targetSlot >= slotCount ||
      placed[targetSlot] != null
    ) {
      stillUnresolved.push(m);
      continue;
    }
    placed[targetSlot] = m;
  }

  // Pass 3: id-order fallback for anything that didn't fit.
  return fillRemainingByIdOrder(placed, stillUnresolved, slotCount);
}

const r16Cells = computed(() =>
  placeByFeeder('round_of_16', r32Matches.value, 8)
);
const qfCells = computed(() =>
  placeByFeeder('quarterfinal', r16Cells.value, 4)
);
const sfCells = computed(() => placeByFeeder('semifinal', qfCells.value, 2));
const finalCell = computed(() => placeByFeeder('final', sfCells.value, 1)[0]);

// ── Inline child component for match cells ──
const BracketCell = {
  props: {
    match: { type: Object, default: null },
    isFinal: { type: Boolean, default: false },
  },
  emits: ['click'],
  setup(p, { emit }) {
    const homeWinner = computed(() => isWinner(p.match, 'home'));
    const awayWinner = computed(() => isWinner(p.match, 'away'));
    const statusLabel = computed(() => {
      if (!p.match) return null;
      if (p.match.match_status === 'completed') return 'Final';
      if (p.match.match_status === 'in_progress') return 'Live';
      if (p.match.match_status === 'cancelled') return 'Cancelled';
      return null;
    });

    return () => {
      if (!p.match) {
        return h(
          'div',
          {
            class: [
              'h-full rounded-md border border-dashed border-gray-200 bg-gray-50/50 flex items-center justify-center text-gray-300 text-xs',
              p.isFinal ? 'px-3 py-2' : 'px-2 py-1.5',
            ],
          },
          '—'
        );
      }
      const live = p.match.match_status === 'in_progress';
      return h(
        'button',
        {
          type: 'button',
          onClick: () => emit('click', p.match),
          class: [
            'w-full text-left rounded-md border bg-white px-2 py-1.5 shadow-sm hover:border-brand-400 transition-colors',
            live ? 'border-brand-400 animate-pulse' : 'border-gray-200',
          ],
        },
        [
          // Row 1: home team
          h(
            'div',
            {
              class: [
                'flex items-center justify-between gap-2 text-xs',
                homeWinner.value
                  ? 'font-bold text-gray-900'
                  : p.match.match_status === 'completed'
                    ? 'text-gray-400'
                    : 'text-gray-800',
              ],
            },
            [
              h(
                'span',
                { class: 'truncate min-w-0' },
                p.match.home_team?.name || 'TBD'
              ),
              h(
                'span',
                { class: 'font-mono tabular-nums shrink-0' },
                scoreCell(p.match, 'home')
              ),
            ]
          ),
          // Row 2: away team
          h(
            'div',
            {
              class: [
                'flex items-center justify-between gap-2 text-xs mt-0.5',
                awayWinner.value
                  ? 'font-bold text-gray-900'
                  : p.match.match_status === 'completed'
                    ? 'text-gray-400'
                    : 'text-gray-800',
              ],
            },
            [
              h(
                'span',
                { class: 'truncate min-w-0' },
                p.match.away_team?.name || 'TBD'
              ),
              h(
                'span',
                { class: 'font-mono tabular-nums shrink-0' },
                scoreCell(p.match, 'away')
              ),
            ]
          ),
          // Row 3: meta (date + status)
          h(
            'div',
            {
              class:
                'mt-1 flex items-center justify-between text-[10px] text-gray-400',
            },
            [
              h('span', null, formatMatchDate(p.match.match_date)),
              statusLabel.value
                ? h(
                    'span',
                    {
                      class: live
                        ? 'text-brand-600 font-semibold'
                        : statusLabel.value === 'Final'
                          ? 'text-green-600 font-semibold'
                          : statusLabel.value === 'Cancelled'
                            ? 'text-red-500'
                            : '',
                    },
                    statusLabel.value
                  )
                : null,
            ]
          ),
        ]
      );
    };
  },
};

// ── helpers ──

function isWinner(match, side) {
  if (!match || match.match_status !== 'completed') return false;
  const h = match.home_score;
  const a = match.away_score;
  if (h == null || a == null) return false;
  // PK shootout wins handled via penalty scores when regulation is tied.
  if (h === a) {
    const hp = match.home_penalty_score;
    const ap = match.away_penalty_score;
    if (hp == null || ap == null) return false;
    return side === 'home' ? hp > ap : ap > hp;
  }
  return side === 'home' ? h > a : a > h;
}

function scoreCell(match, side) {
  if (match.home_score == null || match.away_score == null) return 'TBD';
  const base = side === 'home' ? match.home_score : match.away_score;
  if (match.home_penalty_score != null && match.away_penalty_score != null) {
    const pk =
      side === 'home' ? match.home_penalty_score : match.away_penalty_score;
    return `${base} (${pk})`;
  }
  return String(base);
}

function formatMatchDate(d) {
  if (!d) return '';
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}
</script>

<style scoped>
/*
 * Single-elimination 32-team bracket on a CSS grid.
 *
 * 32 row tracks let each round-cell span the right number of rows to
 * center it vertically against its parent: R32 spans 2, R16 spans 4,
 * QF spans 8, SF spans 16, Final spans 32. The connector lines are
 * drawn with ::before/::after pseudo-elements on each cell.
 */
.bracket-grid {
  display: grid;
  grid-template-columns:
    minmax(170px, 1fr) minmax(170px, 1fr) minmax(170px, 1fr)
    minmax(170px, 1fr) minmax(170px, 1fr);
  grid-template-rows: auto repeat(32, minmax(28px, 1fr));
  gap: 0;
  position: relative;
}

.bracket-header {
  grid-row: 1;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(107 114 128);
  text-align: center;
  padding-bottom: 0.5rem;
}
.col-1 {
  grid-column: 1;
}
.col-2 {
  grid-column: 2;
}
.col-3 {
  grid-column: 3;
}
.col-4 {
  grid-column: 4;
}
.col-5 {
  grid-column: 5;
}

.bracket-cell {
  position: relative;
  padding: 4px 12px 4px 4px;
  display: flex;
  align-items: center;
}
.col-2.bracket-cell,
.col-3.bracket-cell,
.col-4.bracket-cell,
.col-5.bracket-cell {
  padding-left: 12px;
}

.bracket-cell > * {
  width: 100%;
}

/* R32: rows 2..33 in pairs of 2 */
.r32-0 {
  grid-row: 2 / span 2;
}
.r32-1 {
  grid-row: 4 / span 2;
}
.r32-2 {
  grid-row: 6 / span 2;
}
.r32-3 {
  grid-row: 8 / span 2;
}
.r32-4 {
  grid-row: 10 / span 2;
}
.r32-5 {
  grid-row: 12 / span 2;
}
.r32-6 {
  grid-row: 14 / span 2;
}
.r32-7 {
  grid-row: 16 / span 2;
}
.r32-8 {
  grid-row: 18 / span 2;
}
.r32-9 {
  grid-row: 20 / span 2;
}
.r32-10 {
  grid-row: 22 / span 2;
}
.r32-11 {
  grid-row: 24 / span 2;
}
.r32-12 {
  grid-row: 26 / span 2;
}
.r32-13 {
  grid-row: 28 / span 2;
}
.r32-14 {
  grid-row: 30 / span 2;
}
.r32-15 {
  grid-row: 32 / span 2;
}

/* R16: each spans 4 rows, centered between its two R32 parents */
.r16-0 {
  grid-row: 2 / span 4;
}
.r16-1 {
  grid-row: 6 / span 4;
}
.r16-2 {
  grid-row: 10 / span 4;
}
.r16-3 {
  grid-row: 14 / span 4;
}
.r16-4 {
  grid-row: 18 / span 4;
}
.r16-5 {
  grid-row: 22 / span 4;
}
.r16-6 {
  grid-row: 26 / span 4;
}
.r16-7 {
  grid-row: 30 / span 4;
}

/* QF: each spans 8 rows */
.qf-0 {
  grid-row: 2 / span 8;
}
.qf-1 {
  grid-row: 10 / span 8;
}
.qf-2 {
  grid-row: 18 / span 8;
}
.qf-3 {
  grid-row: 26 / span 8;
}

/* SF: each spans 16 rows */
.sf-0 {
  grid-row: 2 / span 16;
}
.sf-1 {
  grid-row: 18 / span 16;
}

/* Final spans all 32 */
.final-0 {
  grid-row: 2 / span 32;
}

/* Connector lines.
 * For each cell, draw a short horizontal line going right toward the
 * next round, and a vertical line joining sibling pairs.
 *
 * Layout reference:
 *   cell ─┐
 *         │ vertical
 *   cell ─┘
 *         ── horizontal (drawn from the next column's left edge)
 */
.bracket-cell::after {
  /* Short horizontal line going right from this cell's right edge.
   * This is the "lead-out" line common to every cell except Final. */
  content: '';
  position: absolute;
  right: 0;
  top: 50%;
  width: 12px;
  height: 1px;
  background: rgb(209 213 219);
}
.col-5.bracket-cell::after {
  display: none;
}

/*
 * Vertical "bridge" that joins two sibling cells: drawn on the top
 * cell of each pair, extending downward to the bottom cell's midpoint.
 *   For R32→R16: pair = (2k, 2k+1). Top cells: r32-0,2,4,...,14.
 *   For R16→QF: top cells: r16-0,2,4,6.
 *   For QF→SF: top cells: qf-0, qf-2.
 *   For SF→Final: top cell: sf-0.
 * Height of the bridge = vertical distance between paired-cell midpoints
 * = (rows-per-cell) × row-height. Since each pair sits in 2 × span rows,
 * the bridge spans exactly `span` rows downward (= 100% of cell height).
 */
.r32-0::before,
.r32-2::before,
.r32-4::before,
.r32-6::before,
.r32-8::before,
.r32-10::before,
.r32-12::before,
.r32-14::before,
.r16-0::before,
.r16-2::before,
.r16-4::before,
.r16-6::before,
.qf-0::before,
.qf-2::before,
.sf-0::before {
  content: '';
  position: absolute;
  right: 0;
  top: 50%;
  width: 1px;
  height: 100%;
  background: rgb(209 213 219);
}

/* Mobile: keep the bracket usable; rely on the outer overflow-x scroll. */
@media (max-width: 768px) {
  .bracket-grid {
    grid-template-rows: auto repeat(32, minmax(34px, auto));
  }
}
</style>
