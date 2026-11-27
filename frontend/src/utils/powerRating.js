/**
 * Formatting for the Power Rating list (SB-1809), kept pure so the rules that
 * matter — absent is never zero, a rating reads like a rating — are tested
 * without mounting anything.
 */

// The two badges the run stores (`PowerRatingDAO`), short on the chip with
// the rule in the title. Pro academy is a row flag, not a stored badge.
export const BADGES = {
  provisional: {
    label: 'Provisional',
    title: 'Provisional: 6 or 7 matches, so the rating still moves quickly',
  },
  low_cross_conference: {
    label: 'Low cross-conf.',
    title:
      'Low cross-conference data: fewer than 3 matches against other conferences',
  },
};

const MINUS = '−';

/** 1642 -> "1,642". Null stays null: no rating is not a rating of 0. */
export const formatRating = rating =>
  rating == null ? null : Number(rating).toLocaleString('en-US');

/** 1 -> "1st", 12 -> "12th", 22 -> "22nd". */
export const ordinal = n => {
  if (n == null) return null;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'}`;
};

/**
 * Movement over 7 days, as places and points: "▲2 · +12", "▼1 · −8".
 *
 * Null is absent, never "▲0": no run a week earlier (`movementSince` null)
 * renders nothing, and a team that was not in that run reads "New". A rank
 * that held drops its arrow and keeps the points; an unchanged rating is ±0.
 * Returns `{ text, direction }` or null; direction is 'up' | 'down' | 'flat'
 * | 'new'.
 */
export const formatMovement = (rankChange, ratingChange, movementSince) => {
  if (rankChange == null && ratingChange == null) {
    return movementSince ? { text: 'New', direction: 'new' } : null;
  }
  const parts = [];
  if (rankChange > 0) parts.push(`▲${rankChange}`);
  else if (rankChange < 0) parts.push(`▼${Math.abs(rankChange)}`);
  if (ratingChange != null) {
    if (ratingChange > 0) parts.push(`+${ratingChange}`);
    else if (ratingChange < 0) parts.push(`${MINUS}${Math.abs(ratingChange)}`);
    else parts.push('±0');
  }
  // Places lead; with no place change the points decide the colour.
  const lead = rankChange || ratingChange || 0;
  const direction = lead > 0 ? 'up' : lead < 0 ? 'down' : 'flat';
  return { text: parts.join(' · '), direction };
};

/** "2026-12-15T10:00:04Z" -> "Dec 15, 2026"; null for nothing usable. */
export const formatUpdated = computedAt => {
  if (!computedAt) return null;
  const d = new Date(computedAt);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

/**
 * The national list under its tier headers, in the order `tiers` gives.
 * Ranked teams below the lowest cut-off go under "Others"; teams outside the
 * main island (`comparable_nationally` false, no national rank) go last,
 * under their own header, never interleaved into the order.
 */
export const groupByTier = (teams, tiers) => {
  const groups = (tiers || []).map(t => ({
    key: t.key,
    label: t.label,
    hint: `${formatRating(t.min)}+`,
    rows: [],
  }));
  const byKey = Object.fromEntries(groups.map(g => [g.key, g]));
  const lowest = (tiers || []).reduce(
    (min, t) => (min == null || t.min < min ? t.min : min),
    null
  );
  const others = {
    key: 'others',
    label: 'Others',
    hint: lowest == null ? null : `below ${formatRating(lowest)}`,
    rows: [],
  };
  const apart = {
    key: 'not_comparable',
    label: 'Not yet comparable nationally',
    hint: 'shown with their conference',
    rows: [],
  };
  for (const row of teams || []) {
    if (row.comparable_nationally === false || row.rank == null) {
      apart.rows.push(row);
    } else if (row.tier && byKey[row.tier]) {
      byKey[row.tier].rows.push(row);
    } else {
      others.rows.push(row);
    }
  }
  return [...groups, others, apart].filter(g => g.rows.length > 0);
};

// --- the team's "why" panel (SB-1810) ------------------------------------

// The badges in words, for the panel. Same rules as the chip titles.
export const BADGE_EXPLANATIONS = {
  provisional:
    'Provisional: fewer than 8 matches rated, so the rating still moves quickly.',
  low_cross_conference:
    'Low cross-conference data: fewer than 3 matches against teams outside its conference, so its place against other conferences is less certain.',
};

const VERB = { W: 'Beat', D: 'Drew with', L: 'Lost to' };

/** 24.4 -> "+24", -57 -> "−57", 0.3 -> "±0". Whole points, as the rating is shown. */
export const formatDelta = delta => {
  if (delta == null) return null;
  const n = Math.round(delta);
  if (n > 0) return `+${n}`;
  if (n < 0) return `${MINUS}${Math.abs(n)}`;
  return '±0';
};

/** "2026-12-14" -> "Dec 14", read as a calendar date (no timezone shift). */
export const formatMatchDate = isoDate => {
  if (!isoDate) return null;
  const [y, m, d] = String(isoDate).slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
};

/**
 * One of the matches that moved the rating most, as a sentence:
 * `{ headline: "Beat NEFC U17 3–0", delta: "+24", detail: [...] }`.
 *
 * `expected` is the share of the points the team was expected to take, a draw
 * counting half, so it reads "expected to take 41% of the points" rather than
 * a win chance. A shoot-out keeps its regulation score and says it was rated
 * as a draw. A score the match row no longer has is left out, never 0–0.
 */
export const formatMover = move => {
  const score =
    move.goals_for != null && move.goals_against != null
      ? ` ${move.goals_for}–${move.goals_against}`
      : '';
  const detail = [];
  const date = formatMatchDate(move.match_date);
  if (date) detail.push(date);
  const pf = move.penalties_for;
  const pa = move.penalties_against;
  if (pf != null && pa != null && pf !== pa) {
    const how = pf > pa ? 'Won' : 'Lost';
    detail.push(`${how} ${pf}–${pa} on penalties, rated as a draw`);
  }
  if (move.expected != null) {
    detail.push(
      `expected to take ${Math.round(move.expected * 100)}% of the points`
    );
  }
  return {
    headline: `${VERB[move.result] || 'Played'} ${move.opponent}${score}`,
    delta: formatDelta(move.delta),
    direction: move.delta > 0 ? 'up' : move.delta < 0 ? 'down' : 'flat',
    detail: detail.join(' · '),
  };
};

/**
 * Strength of schedule: "Average opponent 1,538 — 12th toughest of 147".
 * The rank always comes with its denominator; with no rank (an unranked
 * team, or no peers to rank against) only the average is stated. A
 * conference-scoped rank names the conference, since separate conferences
 * are not on one scale.
 */
export const formatSos = (sos, conference) => {
  if (!sos || sos.rating == null) return null;
  const average = `Average opponent ${formatRating(sos.rating)}`;
  if (sos.rank == null || sos.of == null) return average;
  const where =
    sos.scope === 'conference' && conference ? ` in ${conference}` : '';
  return `${average} — ${ordinal(sos.rank)} toughest of ${sos.of}${where}`;
};

/**
 * Points for an inline SVG sparkline over `history` (one per week, oldest
 * first) in a `width` × `height` box. Fewer than 2 points draws no line.
 */
export const sparkline = (history, width = 200, height = 40, pad = 3) => {
  const values = (history || []).map(h => h.rating).filter(v => v != null);
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = (width - 2 * pad) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = pad + i * step;
    // A flat history sits in the middle rather than on the floor.
    const y =
      max === min
        ? height / 2
        : height - pad - ((v - min) / span) * (height - 2 * pad);
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
  });
  return {
    points: pts.map(p => p.join(',')).join(' '),
    first: pts[0],
    last: pts[pts.length - 1],
  };
};
