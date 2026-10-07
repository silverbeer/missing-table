/**
 * Which age group a filtered view opens on when this browser has no
 * remembered pick (SB-1286).
 *
 * Precedence, first one that exists in `ageGroups` wins:
 *   1. the account's saved preference (profile.preferences.default_age_group_id)
 *   2. the age group of the viewer's current-season team (SB-599)
 *   3. U14, the anonymous fallback
 *
 * The remembered pick (useFilterMemory, SB-1112) sits above all three and is
 * applied by the view itself — last pick wins.
 *
 * Preferences live in jsonb with no foreign key, so a saved id can name an age
 * group that no longer exists. That falls through to the next rung rather than
 * selecting something the dropdown cannot show.
 */
export const pickDefaultAgeGroupId = ({ preferred, team, ageGroups }) => {
  const list = ageGroups || [];
  const known = new Set(list.map(ag => Number(ag.id)));
  for (const id of [preferred, team]) {
    if (id !== null && id !== undefined && known.has(Number(id))) {
      return Number(id);
    }
  }
  const u14 = list.find(ag => ag.name === 'U14');
  return u14 ? u14.id : null;
};
