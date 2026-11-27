/**
 * The Power Rating's per-match update (power-rating.md "The model"), for the
 * How it works screen (SB-1811). The backend recompute job is the rating of
 * record; this copy exists so the worked example on screen is computed from
 * the formula it states rather than typed in, and a test holds both to it.
 */

export const START = 1500;
export const HOME_EDGE = 50;
export const K = 30;
export const K_PROVISIONAL = 60;
export const PROVISIONAL_MATCHES = 8;

/** Share of the points a team is expected to take; a draw counts half. */
export const expectedScore = (rTeam, rOpp, home = 0) =>
  1 / (1 + 10 ** (-(rTeam - rOpp + home) / 400));

/** G: 1 for a draw or 1-goal margin, 1.5 for 2 goals, 1.75 for 3 or more. */
export const marginFactor = goalDiff => {
  const margin = Math.abs(goalDiff);
  if (margin >= 3) return 1.75;
  if (margin === 2) return 1.5;
  return 1;
};

/** K × G × (S − E) for one side of a match, unrounded. */
export const ratingChange = ({
  rating,
  opponent,
  home = 0,
  goalsFor,
  goalsAgainst,
  k = K,
}) => {
  const diff = goalsFor - goalsAgainst;
  const s = diff > 0 ? 1 : diff < 0 ? 0 : 0.5;
  const e = expectedScore(rating, opponent, home);
  return k * marginFactor(diff) * (s - e);
};
