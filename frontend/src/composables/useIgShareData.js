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

// Filter the backend's "Unknown" sentinel — see match_dao.get_match_by_id,
// which substitutes "Unknown" when a relation (division, season, etc.) is
// null. Without this filter the share card would print "UNKNOWN" for
// tournament matches that have no division.
const cleanName = v => (v && v !== 'Unknown' && v !== 'unknown' ? v : null);

export function useIgShareData(matchRef, modeRef) {
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

  // True when match has tournament context — drives whether the
  // Tournament Round template is offered as an option in the picker.
  const hasTournamentRound = computed(() => !!tournamentRoundLabel.value);

  // The Homegrown league is the user-facing name for the MLS Next
  // pathway. When true, each template renders an "MLS Next" badge so
  // the card visually associates the match with the broader league.
  const leagueName = computed(
    () => matchRef.value?.division?.leagues?.name || null
  );
  const isHomegrownLeague = computed(() => leagueName.value === 'Homegrown');

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
    leagueName,
    isHomegrownLeague,
  };
}
