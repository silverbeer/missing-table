/**
 * Tournament Match of the Day — which picks the page shows (SB-1750).
 *
 * A pick is one per (tournament, day, age group), so a multi-age tournament
 * can hold several for the same day. The banner follows the age group being
 * viewed: that age group's pick, or nothing — never another age group's.
 */

/**
 * A pick's age group id. Picks from before the SB-1750 migration may lack
 * `age_group_id`; their match still says which age group it is.
 */
export function pickAgeGroupId(pick) {
  return (
    pick?.age_group_id ??
    pick?.match?.age_group_id ??
    pick?.match?.age_group?.id ??
    null
  );
}

/**
 * The picks to show as banners, in the order the API returned them (by age
 * group within a day).
 *
 * - `today`: the viewer's local date key (`localDateKey()`); only that day's
 *   picks are shown.
 * - `ageGroupId`: the age group on screen. `null` is "All Ages": every pick
 *   for the day. A single-age tournament has one, so it shows one banner.
 *
 * No pick for the viewed age group is `[]`: absent renders as absent.
 */
export function picksForView(picks, { today, ageGroupId = null } = {}) {
  if (!Array.isArray(picks) || !today) return [];
  const todays = picks.filter(
    p => p && String(p.match_date).slice(0, 10) === today
  );
  if (ageGroupId == null) return todays;
  const pick = todays.find(p => pickAgeGroupId(p) === ageGroupId);
  return pick ? [pick] : [];
}
