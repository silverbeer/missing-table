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

export function useIgShareData(matchRef, modeRef, eventsRef) {
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

  const metaLabel = computed(() => {
    const parts = [];
    const matchType = cleanName(matchRef.value?.match_type_name);
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
    homeScore,
    awayScore,
    homeInitials,
    awayInitials,
    ageGroupLabel,
    metaLabel,
    tournamentName,
    tournamentGroup,
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
