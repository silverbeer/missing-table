// Standings cell formatting (SB-1623). Android and iOS format the same way:
// per-match rates to exactly 2 decimals, a sign on positive goal
// differences, and a dash — never 0.00 — for a rate a team doesn't have yet.

export const MISSING = '–';

const isNumber = value => typeof value === 'number' && Number.isFinite(value);

const signed = text => (Number(text) > 0 ? `+${text}` : text);

// "-0.00" reads as a negative rate that isn't one.
const fixed2 = value => {
  const text = value.toFixed(2);
  return text === '-0.00' ? '0.00' : text;
};

/**
 * @param {unknown} value
 * @param {'count'|'signed'|'rate'|'signedRate'} format
 */
export function formatStat(value, format = 'count') {
  if (!isNumber(value))
    return format === 'count' ? String(value ?? MISSING) : MISSING;
  switch (format) {
    case 'rate':
      return fixed2(value);
    case 'signedRate':
      return signed(fixed2(value));
    case 'signed':
      return signed(String(value));
    default:
      return String(value);
  }
}

const muted = 'text-fg-muted';

// One list drives header and cells, in the order every client shows them.
// GP, Pts and PPM lead so a phone shows why a team sits where it does
// before any scrolling: 9 from 4 (2.25) above 11 from 5 (2.20).
export const STAT_COLUMNS = [
  {
    key: 'played',
    label: 'GP',
    title: 'Games played',
    testid: 'played',
    cellClass: muted,
  },
  {
    key: 'points',
    label: 'Pts',
    title: 'Points',
    testid: 'points',
    cellClass: 'font-bold text-accent-600 dark:text-accent-300',
    headClass: 'text-brand-200',
  },
  {
    key: 'points_per_match',
    label: 'PPM',
    title: 'Points per match. The table is ranked by this.',
    testid: 'points-per-match',
    format: 'rate',
    cellClass: 'font-semibold text-fg',
    headClass: 'text-brand-200',
  },
  { key: 'wins', label: 'W', title: 'Wins', testid: 'wins', cellClass: muted },
  {
    key: 'draws',
    label: 'D',
    title: 'Draws',
    testid: 'draws',
    cellClass: muted,
  },
  {
    key: 'losses',
    label: 'L',
    title: 'Losses',
    testid: 'losses',
    cellClass: muted,
  },
  {
    key: 'goals_for',
    label: 'GF',
    title: 'Goals for',
    testid: 'goals-for',
    cellClass: muted,
  },
  {
    key: 'goals_against',
    label: 'GA',
    title: 'Goals against',
    testid: 'goals-against',
    cellClass: muted,
  },
  {
    key: 'goal_difference',
    label: 'GD',
    title: 'Goal difference',
    testid: 'goal-difference',
    format: 'signed',
    cellClass: muted,
  },
  {
    key: 'gd_per_match',
    label: 'GD/M',
    title: 'Goal difference per match',
    testid: 'gd-per-match',
    format: 'signedRate',
    cellClass: muted,
  },
  {
    key: 'gf_per_match',
    label: 'GF/M',
    title: 'Goals for per match',
    testid: 'gf-per-match',
    format: 'rate',
    cellClass: muted,
  },
  {
    key: 'ga_per_match',
    label: 'GA/M',
    title: 'Goals against per match',
    testid: 'ga-per-match',
    format: 'rate',
    cellClass: muted,
  },
];

/**
 * Column sort that keeps league order for ties and puts a missing value
 * (a team with no games has no rate) last in either direction.
 */
export function compareByColumn(a, b, key, direction) {
  const av = a[key];
  const bv = b[key];
  const aMissing = !isNumber(av);
  const bMissing = !isNumber(bv);
  if (aMissing !== bMissing) return aMissing ? 1 : -1;
  if (aMissing || av === bv) return a.standingsRank - b.standingsRank;
  return (av - bv) * direction;
}
