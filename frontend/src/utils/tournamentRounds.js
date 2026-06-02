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
};

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
