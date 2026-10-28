/**
 * Playing up: when a match may pair teams from different age groups (SB-1443).
 *
 * Pro academies routinely play up an age group in friendlies, and Homegrown
 * teams play up in lower-level tournaments. A match still carries one age
 * group, so the opponent from another age group has no registration there —
 * and a picker that offers only registered teams can never schedule it.
 *
 * League and Flex stay strict: their fixtures feed standings, and a cross-age
 * pairing there is a data error, not a match.
 */
const PLAYING_UP_MATCH_TYPES = new Set(['friendly', 'tournament']);

export const allowsPlayingUp = matchTypeName =>
  PLAYING_UP_MATCH_TYPES.has((matchTypeName || '').trim().toLowerCase());

/**
 * Split a team list into the teams registered for the match's age group and
 * every other team, so a picker can offer both without burying the usual
 * choice. `others` is empty unless the match type allows playing up.
 */
export const groupTeamsForMatch = ({ registered, all, playingUp }) => {
  const reg = registered || [];
  if (!playingUp) return { registered: reg, others: [] };
  const seen = new Set(reg.map(t => t.id));
  const others = (all || [])
    .filter(t => !seen.has(t.id))
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  return { registered: reg, others };
};
