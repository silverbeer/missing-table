import { describe, it, expect } from 'vitest';
import { pickAgeGroupId, picksForView } from '@/utils/tournamentMotd';

const TODAY = '2026-12-04';
const TOMORROW = '2026-12-05';
const U15 = 2;
const U16 = 3;
const U17 = 4;

const pick = (matchId, ageGroupId, date = TODAY, over = {}) => ({
  tournament_id: 12,
  match_date: date,
  age_group_id: ageGroupId,
  match: { id: matchId, age_group_id: ageGroupId },
  ...over,
});

const ids = picks => picks.map(p => p.match.id);

describe('pickAgeGroupId', () => {
  it("reads the pick's own age group first", () => {
    expect(pickAgeGroupId(pick(501, U15))).toBe(U15);
  });

  it("falls back to the match's age group for a pick without one", () => {
    expect(pickAgeGroupId({ match: { id: 1, age_group_id: U16 } })).toBe(U16);
    expect(pickAgeGroupId({ match: { id: 1, age_group: { id: U17 } } })).toBe(
      U17
    );
  });

  it('is null when nothing says which age group', () => {
    expect(pickAgeGroupId({ match: { id: 1 } })).toBe(null);
    expect(pickAgeGroupId(null)).toBe(null);
  });
});

describe('picksForView', () => {
  const BOTH = [pick(501, U15), pick(601, U16)];

  it('shows only the viewed age group when two are picked the same day', () => {
    expect(ids(picksForView(BOTH, { today: TODAY, ageGroupId: U15 }))).toEqual([
      501,
    ]);
    expect(ids(picksForView(BOTH, { today: TODAY, ageGroupId: U16 }))).toEqual([
      601,
    ]);
  });

  it("shows nothing for an age group with no pick, not another age's pick", () => {
    expect(picksForView(BOTH, { today: TODAY, ageGroupId: U17 })).toEqual([]);
  });

  it("matches a legacy pick without age_group_id by its match's age group", () => {
    const legacyFlat = {
      match_date: TODAY,
      match: { id: 701, age_group_id: U16 },
    };
    const legacyNested = {
      match_date: TODAY,
      match: { id: 702, age_group: { id: U15, name: 'U15' } },
    };
    const picks = [legacyNested, legacyFlat];
    expect(ids(picksForView(picks, { today: TODAY, ageGroupId: U16 }))).toEqual(
      [701]
    );
    expect(ids(picksForView(picks, { today: TODAY, ageGroupId: U15 }))).toEqual(
      [702]
    );
    expect(picksForView(picks, { today: TODAY, ageGroupId: U17 })).toEqual([]);
  });

  it("shows every pick for today under All Ages, in the API's order", () => {
    const picks = [pick(501, U15), pick(601, U16), pick(701, U17)];
    expect(
      ids(picksForView(picks, { today: TODAY, ageGroupId: null }))
    ).toEqual([501, 601, 701]);
    // No age group named at all is All Ages too.
    expect(ids(picksForView(picks, { today: TODAY }))).toEqual([501, 601, 701]);
  });

  it('ignores a pick for another day', () => {
    const picks = [pick(501, U15, TOMORROW), pick(601, U16)];
    expect(picksForView(picks, { today: TODAY, ageGroupId: U15 })).toEqual([]);
    expect(
      ids(picksForView(picks, { today: TODAY, ageGroupId: null }))
    ).toEqual([601]);
  });

  it('compares the day, not the timestamp', () => {
    const picks = [pick(501, U15, `${TODAY}T00:00:00+00:00`)];
    expect(ids(picksForView(picks, { today: TODAY, ageGroupId: U15 }))).toEqual(
      [501]
    );
  });

  it('shows the one pick of a single-age tournament, viewed either way', () => {
    const picks = [pick(401, U15, '2026-12-03'), pick(501, U15)];
    expect(
      ids(picksForView(picks, { today: TODAY, ageGroupId: null }))
    ).toEqual([501]);
    expect(ids(picksForView(picks, { today: TODAY, ageGroupId: U15 }))).toEqual(
      [501]
    );
  });

  it('is empty for no picks, a non-list, or no day', () => {
    expect(picksForView([], { today: TODAY, ageGroupId: U15 })).toEqual([]);
    expect(picksForView(null, { today: TODAY })).toEqual([]);
    expect(picksForView(BOTH, {})).toEqual([]);
    expect(picksForView(BOTH)).toEqual([]);
  });
});
