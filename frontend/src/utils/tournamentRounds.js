// Single source of truth for tournament round display labels.
//
// Matches carry a `tournament_round` key (e.g. "quarterfinal"). Different
// surfaces want different verbosity:
//   - compact bracket / match-center views use short labels ("QF")
//   - admin and detail views use full labels ("Quarterfinal")

export const TOURNAMENT_ROUNDS = {
  group_stage: { short: 'Group Stage', long: 'Group Stage' },
  round_of_32: { short: 'R32', long: 'Round of 32' },
  round_of_16: { short: 'R16', long: 'Round of 16' },
  quarterfinal: { short: 'QF', long: 'Quarterfinal' },
  semifinal: { short: 'SF', long: 'Semifinal' },
  third_place: { short: '3rd Place', long: 'Third Place' },
  final: { short: 'Final', long: 'Final' },
  // MLS NEXT Fest (SB-1752). Real rounds, but not an elimination tree: none of
  // these is a knockout or bracket round, so a tournament whose only "finals"
  // are placement finals does not switch on the bracket view.
  showcase: { short: 'Showcase', long: 'Showcase' },
  consolation: { short: 'Consolation', long: 'Consolation' },
  placement_final: { short: 'Placement', long: 'Placement Final' },
};

// Elimination rounds in playing order (R32 → R16 → QF → SF → 3rd → Final).
export const KNOCKOUT_ROUND_ORDER = [
  'round_of_32',
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'third_place',
  'final',
];

export const KNOCKOUT_ROUNDS = new Set(KNOCKOUT_ROUND_ORDER);

// The rounds the bracket view draws, one column each. The third-place match is
// a knockout round but sits outside the tree, so it has no column.
export const BRACKET_ROUND_ORDER = KNOCKOUT_ROUND_ORDER.filter(
  round => round !== 'third_place'
);

export const BRACKET_ROUNDS = new Set(BRACKET_ROUND_ORDER);

// Rounds where a level score has to be broken, so the score editor offers
// shootout inputs. Wider than KNOCKOUT_ROUNDS: consolation and placement
// matches need a winner too, without being part of the knockout tree.
export const SHOOTOUT_ROUNDS = new Set([
  ...KNOCKOUT_ROUND_ORDER,
  'consolation',
  'placement_final',
]);

export const ROUND_LABELS_SHORT = Object.fromEntries(
  Object.entries(TOURNAMENT_ROUNDS).map(([key, { short }]) => [key, short])
);

export const ROUND_LABELS_LONG = Object.fromEntries(
  Object.entries(TOURNAMENT_ROUNDS).map(([key, { long }]) => [key, long])
);

// Resolve a round key to a label. Returns null for unknown/empty rounds.
export function roundLabel(round, { short = false } = {}) {
  const entry = TOURNAMENT_ROUNDS[round];
  if (!entry) return null;
  return short ? entry.short : entry.long;
}
