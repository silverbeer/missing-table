/**
 * useIgShareData — shared computed properties for the IG share-card
 * templates (SB-32).
 *
 * All four templates (Overlay, Split, TournamentRound, Stadium) share
 * the same underlying match data and the same rules for what to display
 * (e.g. tournament_name beats division, "Unknown" is filtered out, etc.).
 * Each template renders these values differently — this composable is
 * the single source of truth for the values themselves.
 */

import { computed } from 'vue';

// Promotional CTA shown at the bottom of every IG share-card template.
// The preview (pre-match) variant nudges followers to come watch live;
// the result (full-time) variant pivots to invite acquisition since the
// match is already over. Single source so copy changes are one edit.
export const IG_SHARE_TAGLINE =
  'Check out missingtable.com for live match updates';
export const IG_SHARE_RESULT_TAGLINE =
  'Go to missingtable.com to request an invite';

const initialsFor = name => {
  if (!name) return '?';
  return name
    .split(' ')
    .map(word => word[0])
    .filter(Boolean)
    .join('')
    .slice(0, 3)
    .toUpperCase();
};

// The dark ground the cards are drawn on, and MT's own accent used
// whenever a club color can't be trusted. Kept here so the contrast
// math and the templates agree on one value.
export const CARD_GROUND = '#0B0B0D';
export const MT_ACCENT = '#FFC400';

// Seeded placeholder written for clubs nobody has branded yet. It is a
// gray stand-in, not a brand color, so it must never drive the accent.
const PLACEHOLDER_CLUB_COLORS = new Set(['#6b7280', '#374151']);

// Deliberately below WCAG's 3:1 floor for graphical elements. That bar
// is calibrated for small UI indicators that must be picked out at a
// glance; the accent here is a large filled block (chip, footer band,
// torn-edge underlay) where much less contrast still reads clearly.
//
// Calibrated against New York Red Bulls' #B22222, which scores 2.94:1
// on this ground. It is an obviously visible red, and rejecting a real
// club's brand color over 0.06 of a ratio point would be the wrong
// trade. The dark colors this needs to catch are far below: #00008B is
// 1.29, #0A2240 is 1.23, #000000 is 0.94.
const MIN_ACCENT_CONTRAST = 2.5;

// How long after a season opens a friendly still counts as preseason.
//
// Bounded by the real fixtures on both sides: the Aug 2026 friendlies
// sit 22 days after the 2026-2027 opening and must be caught, while the
// Oct 2025 friendlies sit 40 days after the 2025-2026 opening and must
// not be. 30 days separates them with room either way.
const PRESEASON_WINDOW_DAYS = 30;

const isPlaceholderClubColor = hex =>
  PLACEHOLDER_CLUB_COLORS.has(String(hex).trim().toLowerCase());

const parseHex = hex => {
  let h = String(hex).trim().replace('#', '');
  if (h.length === 3) {
    h = h
      .split('')
      .map(c => c + c)
      .join('');
  }
  if (!/^[0-9a-fA-F]{6}$/.test(h)) return null;
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
};

// WCAG relative luminance.
const relativeLuminance = hex => {
  const rgb = parseHex(hex);
  if (!rgb) return 0;
  const [r, g, b] = rgb.map(v => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const contrastRatio = (a, b) => {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
};

// Format a goal event's minute the same way the in-app scoreboard does
// (MatchDetailView.formatMinute): "22'" or, with stoppage time, "90+5'".
const formatGoalMinute = event => {
  if (!event?.match_minute) return '';
  if (event.extra_time) {
    return `${event.match_minute}+${event.extra_time}'`;
  }
  return `${event.match_minute}'`;
};

// Identity key for tallying a player's goals across the match. Prefer the
// stable player_id; fall back to the displayed name scoped to the team —
// live-scored youth matches often store only a jersey number like "#9"
// with no id, and that number is unique only within a team (both sides
// can field a #9). Goals with neither id nor name stay unique so they
// never group into a phantom brace/hat-trick.
const scorerKey = event => {
  if (event?.player_id != null) return `id:${event.player_id}`;
  if (event?.player_name)
    return `team:${event.team_id}|name:${event.player_name}`;
  return `ev:${event?.id}`;
};

// Chronological sort: match minute, then stoppage time, then insertion id
// as a stable tiebreak for goals logged in the same minute.
const byGoalTime = (a, b) =>
  (a.match_minute || 0) - (b.match_minute || 0) ||
  (a.extra_time || 0) - (b.extra_time || 0) ||
  (a.id || 0) - (b.id || 0);

// Filter the backend's "Unknown" sentinel — see match_dao.get_match_by_id,
// which substitutes "Unknown" when a relation (division, season, etc.) is
// null. Without this filter the share card would print "UNKNOWN" for
// tournament matches that have no division.
const cleanName = v => (v && v !== 'Unknown' && v !== 'unknown' ? v : null);

/**
 * Is this club color usable as the card accent?
 *
 * Rejects the seeded placeholder gray (a stand-in, not a brand decision)
 * and anything too dark to see on the card ground. Exported so the modal
 * can explain why an option is greyed out instead of silently swapping
 * the color the user asked for.
 */
export const isUsableAccent = hex =>
  !!hex &&
  !isPlaceholderClubColor(hex) &&
  contrastRatio(hex, CARD_GROUND) >= MIN_ACCENT_CONTRAST;

/**
 * @param matchRef  ref to the match
 * @param modeRef   ref to 'preview' | 'result'
 * @param eventsRef ref to match events
 * @param accentPreferenceRef optional ref to 'auto' | 'home' | 'away' | 'mt'.
 *   'auto' keeps the automatic home-then-away-then-MT resolution. An
 *   explicit side is honoured when that club's color is usable, and falls
 *   back rather than emitting an invisible accent.
 */
export function useIgShareData(
  matchRef,
  modeRef,
  eventsRef,
  accentPreferenceRef = null
) {
  const homeTeamName = computed(() => matchRef.value?.home_team_name || '');
  const awayTeamName = computed(() => matchRef.value?.away_team_name || '');
  const homeLogoUrl = computed(
    () => matchRef.value?.home_team_club?.logo_url || null
  );
  const awayLogoUrl = computed(
    () => matchRef.value?.away_team_club?.logo_url || null
  );
  const homeColor = computed(
    () => matchRef.value?.home_team_club?.primary_color || '#3B82F6'
  );
  const awayColor = computed(
    () => matchRef.value?.away_team_club?.primary_color || '#EF4444'
  );
  // Accent color for the card's one bright moment (eyebrow chip, footer
  // band, torn-edge underlay). Prefer the home club's brand color, then
  // the away club's, then MT's own yellow.
  //
  // Two things make this less obvious than "just use the club color":
  //
  // 1. Most clubs have no real color. 105 of 127 sit on the seeded default
  //    #6B7280, which is a gray placeholder, not a brand decision. Treating
  //    it as a brand color would paint most cards the same dead gray.
  // 2. Of the clubs that DO set one, several are navy or near-black
  //    (#00008B, #0A2240, #0b0a0f, #000000). Those vanish against the dark
  //    card ground, so the accent would silently disappear on exactly the
  //    fixtures where a club bothered to set a color.
  //
  // So: skip the placeholder, then require the survivor to actually be
  // visible before using it.
  //
  // SB-659: the automatic order is only a default. Someone posting to their
  // own club's feed wants their own club's colors, which on e.g. Red Bulls
  // vs IFA is the away side — so an explicit preference wins when the
  // chosen club's color is actually usable.
  const accentColor = computed(() => {
    const home = matchRef.value?.home_team_club?.primary_color;
    const away = matchRef.value?.away_team_club?.primary_color;
    const pref = accentPreferenceRef?.value || 'auto';

    if (pref === 'mt') return MT_ACCENT;
    if (pref === 'home' && isUsableAccent(home)) return home;
    if (pref === 'away' && isUsableAccent(away)) return away;

    for (const c of [home, away]) {
      if (isUsableAccent(c)) return c;
    }
    return MT_ACCENT;
  });

  // Text that sits ON the accent (footer band, eyebrow chip). A light
  // accent like MT yellow needs dark text; a dark accent needs white.
  const accentTextColor = computed(() =>
    relativeLuminance(accentColor.value) > 0.45 ? '#0B0B0D' : '#FFFFFF'
  );

  const homeScore = computed(() => matchRef.value?.home_score ?? 0);
  const awayScore = computed(() => matchRef.value?.away_score ?? 0);
  const homeInitials = computed(() => initialsFor(homeTeamName.value));
  const awayInitials = computed(() => initialsFor(awayTeamName.value));

  const ageGroupLabel = computed(
    () => matchRef.value?.age_group_name || 'MATCH'
  );

  const tournamentName = computed(() =>
    cleanName(matchRef.value?.tournament_name)
  );
  const tournamentGroup = computed(() =>
    cleanName(matchRef.value?.tournament_group)
  );
  const tournamentLogoUrl = computed(
    () => matchRef.value?.tournament_logo_url || null
  );

  // Normalize round tokens like "round_of_16" / "quarterfinal" / "final"
  // into a human display. Returns null when no round is set, which the
  // template picker uses to decide whether to surface TournamentRound.
  const tournamentRoundLabel = computed(() => {
    const raw = matchRef.value?.tournament_round;
    if (!raw) return null;
    const normalized = String(raw).toLowerCase().replace(/[_-]+/g, ' ').trim();
    const map = {
      'round of 64': 'Round of 64',
      'round of 32': 'Round of 32',
      'round of 16': 'Round of 16',
      'round of 8': 'Quarterfinal',
      quarterfinal: 'Quarterfinal',
      quarterfinals: 'Quarterfinals',
      semifinal: 'Semifinal',
      semifinals: 'Semifinals',
      final: 'Final',
      'third place': 'Third Place',
      'group stage': 'Group Stage',
    };
    return map[normalized] || normalized.replace(/\b\w/g, c => c.toUpperCase());
  });

  // A friendly played in the run-up to the season proper is a preseason
  // friendly, and that is what the card should say — "Friendly" alone
  // undersells a fixture people are travelling to.
  //
  // There is no preseason flag in the data: match_types holds only
  // League / Tournament / Friendly / Playoff. Nor does comparing against
  // the season start work — 2026-2027 starts 2026-08-01 and these
  // fixtures are late August, so they fall after it, not before.
  //
  // What actually separates preseason from a mid-season friendly is
  // whether competitive play has started yet, so that is what this
  // measures: a friendly inside PRESEASON_WINDOW_DAYS of the season
  // opening. It is a heuristic and it is deliberately narrow — a
  // friendly in October is not preseason and must not be labelled one.
  //
  // Replace with a real `seasons.preseason_end_date` when that lands;
  // this reads it already and only falls back to the window when absent.
  const isPreseasonFriendly = computed(() => {
    const type = cleanName(matchRef.value?.match_type_name);
    if (!type || type.toLowerCase() !== 'friendly') return false;

    const matchDate = matchRef.value?.match_date;
    const seasonStart = matchRef.value?.season_start_date;
    if (!matchDate || !seasonStart) return false;

    const explicitEnd = matchRef.value?.preseason_end_date;
    if (explicitEnd) return matchDate <= explicitEnd;

    const start = new Date(`${seasonStart}T00:00:00`);
    const played = new Date(`${matchDate}T00:00:00`);
    if (Number.isNaN(start.valueOf()) || Number.isNaN(played.valueOf())) {
      return false;
    }

    const days = (played - start) / 86400000;
    return days >= 0 && days <= PRESEASON_WINDOW_DAYS;
  });

  const metaLabel = computed(() => {
    const parts = [];
    const matchType = isPreseasonFriendly.value
      ? 'Preseason Friendly'
      : cleanName(matchRef.value?.match_type_name);
    if (matchType) parts.push(matchType);

    const divisionName = cleanName(matchRef.value?.division_name);
    const seasonName = cleanName(matchRef.value?.season_name);

    if (tournamentName.value) parts.push(tournamentName.value);
    else if (divisionName) parts.push(divisionName);
    else if (seasonName) parts.push(seasonName);

    return parts.join(' · ').toUpperCase();
  });

  const dateLabel = computed(() => {
    const date = matchRef.value?.match_date;
    if (!date) return '';
    const d = new Date(date + 'T00:00:00');
    return d.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  });

  const shortDateLabel = computed(() => {
    const date = matchRef.value?.match_date;
    if (!date) return '';
    const d = new Date(date + 'T00:00:00');
    return d
      .toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
      })
      .toUpperCase();
  });

  const kickoffLabel = computed(() => {
    const iso = matchRef.value?.scheduled_kickoff;
    if (!iso) return null;
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  });

  const isResult = computed(() => modeRef.value === 'result');

  // Mode-aware CTA copy. Preview pre-match nudges live-watching; result
  // post-match pivots to invite acquisition (the match is already over).
  const tagline = computed(() =>
    isResult.value ? IG_SHARE_RESULT_TAGLINE : IG_SHARE_TAGLINE
  );

  // True when match has tournament context — drives whether the
  // Tournament Round template is offered as an option in the picker.
  const hasTournamentRound = computed(() => !!tournamentRoundLabel.value);

  // The Homegrown league is the user-facing name for the MLS Next
  // pathway. When true, each template renders an "MLS Next" badge so
  // the card visually associates the match with the broader league.
  //
  // Detection order:
  //   1. Match's division → league (regular-season matches)
  //   2. Either team's primary league (tournament matches have no
  //      division of their own, so we fall back to team membership)
  const leagueName = computed(
    () => matchRef.value?.division?.leagues?.name || null
  );
  const isHomegrownLeague = computed(() => {
    const m = matchRef.value;
    if (!m) return false;
    return (
      leagueName.value === 'Homegrown' ||
      m.home_team_league_name === 'Homegrown' ||
      m.away_team_league_name === 'Homegrown'
    );
  });

  // --- Goal scorers (SB-33) ---------------------------------------------
  // Live-scored matches carry per-goal events; templates surface these on
  // the result card. The composable owns the derivation so all four cards
  // agree on ordering and on what counts as a brace / hat-trick.
  const goalEvents = computed(() =>
    (eventsRef?.value || []).filter(e => e?.event_type === 'goal')
  );

  // Goals per scorer across BOTH teams, used to flag multi-goal games.
  const goalCountByScorer = computed(() => {
    const counts = new Map();
    for (const e of goalEvents.value) {
      const key = scorerKey(e);
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return counts;
  });

  // One entry per goal, in chronological order. Each carries the scorer's
  // full-match tally so the template can highlight braces (>=2) and
  // hat-tricks (>=3).
  const buildScorers = teamId =>
    goalEvents.value
      .filter(e => e.team_id === teamId)
      .slice()
      .sort(byGoalTime)
      .map(e => {
        const goalCount = goalCountByScorer.value.get(scorerKey(e)) || 1;
        return {
          id: e.id,
          name: e.player_name || 'Goal',
          minute: formatGoalMinute(e),
          goalCount,
          isMultiGoal: goalCount >= 2,
          isHatTrick: goalCount >= 3,
        };
      });

  const homeScorers = computed(() =>
    buildScorers(matchRef.value?.home_team_id)
  );
  const awayScorers = computed(() =>
    buildScorers(matchRef.value?.away_team_id)
  );
  const hasScorers = computed(
    () => homeScorers.value.length > 0 || awayScorers.value.length > 0
  );

  // Players with 3+ goals, de-duped and ordered by their first goal so the
  // celebration banner reads in match order. 4+ still qualifies — the
  // banner shows the tally.
  const hatTricks = computed(() => {
    const seen = new Set();
    const out = [];
    for (const e of goalEvents.value.slice().sort(byGoalTime)) {
      const key = scorerKey(e);
      if (seen.has(key)) continue;
      const count = goalCountByScorer.value.get(key) || 0;
      if (count >= 3) {
        seen.add(key);
        out.push({ name: e.player_name || 'Goal', count });
      }
    }
    return out;
  });

  return {
    homeTeamName,
    awayTeamName,
    homeLogoUrl,
    awayLogoUrl,
    homeColor,
    awayColor,
    accentColor,
    accentTextColor,
    homeScore,
    awayScore,
    homeInitials,
    awayInitials,
    ageGroupLabel,
    metaLabel,
    tournamentName,
    tournamentGroup,
    tournamentLogoUrl,
    tournamentRoundLabel,
    hasTournamentRound,
    dateLabel,
    shortDateLabel,
    kickoffLabel,
    isResult,
    tagline,
    leagueName,
    isHomegrownLeague,
    homeScorers,
    awayScorers,
    hasScorers,
    hatTricks,
  };
}
